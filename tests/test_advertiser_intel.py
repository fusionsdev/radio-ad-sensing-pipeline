"""Tests for advertiser intelligence extraction."""

from __future__ import annotations

from pathlib import Path

from shared.db import get_connection, migrate, transaction
from worker.advertiser_intel import extract_advertiser_intel, record_advertiser_opportunity


def test_extract_advertiser_intel_from_transcript() -> None:
    text = (
        "Call The Tax Relief Center at 1-800-TAX-HELP now. "
        "Visit taxrelief.example for a free consultation."
    )
    intel = extract_advertiser_intel(
        transcript=text,
        source_keywords=["tax relief", "back taxes"],
    )
    assert intel["phone_number"] is not None
    assert intel["domain"] == "taxrelief.example"
    assert intel["cta"] is not None
    assert "tax relief" in str(intel["offer_summary"]).lower()


def test_record_advertiser_opportunity_never_auto_approves(tmp_path: Path) -> None:
    db_path = tmp_path / "adv.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES ('wbap', 'http://x', 1)"
            )
            station_id = conn.execute("SELECT id FROM stations").fetchone()[0]
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, 'c.wav', 1.0, 2.0, 'done')
                """,
                (station_id,),
            )
            chunk_id = conn.execute("SELECT id FROM chunks").fetchone()[0]
        intel = extract_advertiser_intel(
            transcript="Tax debt relief call 8005551212",
            source_keywords=["tax debt"],
        )
        with transaction(conn):
            inserted = record_advertiser_opportunity(
                conn,
                vertical="tax_relief",
                station_id=station_id,
                chunk_id=chunk_id,
                keyword_hit_id=None,
                hit_ts=100.0,
                source_keywords=["tax debt"],
                audio_clip_path="data/chunks/c.wav",
                intel=intel,
            )
        assert inserted == 1
        row = conn.execute(
            "SELECT approved, vertical FROM advertiser_opportunities"
        ).fetchone()
        assert row["approved"] == 0
        assert row["vertical"] == "tax_relief"
    finally:
        conn.close()
