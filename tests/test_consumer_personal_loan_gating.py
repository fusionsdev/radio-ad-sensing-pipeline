"""Production gating tests for consumer_personal_loan keyword_hits persistence."""

from __future__ import annotations

import pytest

from shared.config import load_loan_keywords
from shared.consumer_personal_loan import filter_keyword_matches_for_persistence
from shared.db import get_connection, migrate, transaction
from worker.keywords import find_keyword_matches, record_keyword_hits


def _gate_and_record(
    db_path: Path,
    *,
    transcript: str,
    keywords=None,
    station_suffix: str = "1",
) -> list[str]:
    """Mirror worker path: match target phrases, classify, persist only if accept."""
    kw = keywords if keywords is not None else load_loan_keywords()
    matches = find_keyword_matches(transcript, kw)
    matches = filter_keyword_matches_for_persistence(transcript, matches)
    if not matches:
        return []

    station_name = f"gate-test-fm-{station_suffix}"
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES (?, 'http://x', 1)",
                (station_name,),
            )
            station_id = conn.execute("SELECT id FROM stations").fetchone()[0]
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, 'chunk.wav', 1000.0, 1090.0, 'done')
                """,
                (station_id,),
            )
            chunk_id = conn.execute("SELECT id FROM chunks").fetchone()[0]
            record_keyword_hits(
                conn,
                station_id=station_id,
                chunk_id=chunk_id,
                hit_ts=1000.0,
                matches=matches,
            )
        rows = conn.execute(
            "SELECT keyword FROM keyword_hits WHERE chunk_id = ? ORDER BY keyword",
            (chunk_id,),
        ).fetchall()
        return [row["keyword"] for row in rows]
    finally:
        conn.close()


@pytest.fixture
def gate_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "gate.db"
    migrate(db_path)
    return db_path


@pytest.mark.parametrize(
    "transcript",
    [
        "Do you owe back taxes to the IRS?",
        "Get term life insurance today.",
        "Need working capital for your small business?",
        "Business funding available in 24 hours.",
        "Debt relief can reduce what you owe.",
        "Mortgage refinance rates are available now.",
        "Student loan forgiveness may help you.",
        "Repair your credit score today.",
        "Apply online for term life insurance.",
        "Funding available for your small business.",
        "We offer financing options for qualified buyers.",
        "Credit assistance programs may help.",
        "Ask about our payment plan today.",
        "Your credit card cash advance fee may apply.",
        "Get a merchant cash advance for your storefront.",
    ],
)
def test_production_gate_rejects_false_positives(gate_db: Path, transcript: str) -> None:
    suffix = str(abs(hash(transcript)) % 10_000_000)
    recorded = _gate_and_record(gate_db, transcript=transcript, station_suffix=suffix)
    assert recorded == []


@pytest.mark.parametrize(
    "transcript",
    [
        "Apply online for a personal loan today.",
        "Get an installment loan with direct deposit.",
        "Bad credit personal loan options are available.",
        "Request a cash loan online.",
        "Loan matching service connects you with lenders.",
        "Emergency loan funds as soon as next business day.",
    ],
)
def test_production_gate_accepts_consumer_loan_intent(
    gate_db: Path,
    transcript: str,
) -> None:
    suffix = str(abs(hash(transcript)) % 10_000_000)
    recorded = _gate_and_record(gate_db, transcript=transcript, station_suffix=suffix)
    assert len(recorded) >= 1


def test_cash_advance_alone_does_not_persist(gate_db: Path) -> None:
    recorded = _gate_and_record(gate_db, transcript="We discussed cash advance options on the news.")
    assert recorded == []


def test_cash_advance_with_loan_intent_persists(gate_db: Path) -> None:
    recorded = _gate_and_record(
        gate_db,
        transcript="Request a cash advance today with fast approval from our online lenders.",
    )
    assert "cash advance" in recorded


def test_target_only_payday_mention_does_not_persist(gate_db: Path) -> None:
    recorded = _gate_and_record(
        gate_db,
        transcript="This segment mentioned payday loans during the news hour.",
    )
    assert recorded == []
