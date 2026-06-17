"""Tests for loan keyword scanning and persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.db import get_connection, migrate, transaction
from shared.models import LoanKeywordEntry
from worker.keywords import find_keyword_matches, record_keyword_hits


def test_find_keyword_matches_case_insensitive() -> None:
    transcript = "Call now for a cash-out refinance and business funding in Dallas."
    matches = find_keyword_matches(
        transcript,
        [
            LoanKeywordEntry(phrase="cash-out refinance", confidence=0.85),
            LoanKeywordEntry(phrase="business funding", confidence=0.85),
            LoanKeywordEntry(phrase="payday loan", confidence=0.70),
        ],
    )
    keywords = {match.keyword for match in matches}
    assert keywords == {"cash-out refinance", "business funding"}


def test_find_keyword_matches_skips_low_confidence_phrases() -> None:
    transcript = "We discussed life insurance and personal loan options on the show."
    matches = find_keyword_matches(
        transcript,
        [
            LoanKeywordEntry(phrase="life insurance", confidence=0.55),
            LoanKeywordEntry(phrase="personal loan", confidence=0.55),
        ],
        min_record_confidence=0.6,
    )
    assert matches == []


def test_find_keyword_matches_phrase_not_single_word_substring() -> None:
    transcript = "Small business optimism index rose again this quarter."
    matches = find_keyword_matches(
        transcript,
        [LoanKeywordEntry(phrase="business loan", confidence=0.70)],
    )
    assert matches == []


def test_find_keyword_matches_returns_excerpt_with_confidence() -> None:
    transcript = "Welcome back. Need business funding today? Call 800-555-1212."
    matches = find_keyword_matches(
        transcript,
        [LoanKeywordEntry(phrase="business funding", confidence=0.85)],
    )
    assert len(matches) == 1
    assert matches[0].confidence == 0.85
    assert matches[0].excerpt.startswith("[confidence=0.85]")
    assert "business funding" in matches[0].excerpt.lower()


def test_find_keyword_matches_empty_inputs() -> None:
    assert find_keyword_matches("", [LoanKeywordEntry(phrase="loan", confidence=0.8)]) == []
    assert find_keyword_matches("some text", []) == []


def test_find_keyword_matches_accepts_legacy_string_list() -> None:
    matches = find_keyword_matches("Need business funding today.", ["business funding"])
    assert len(matches) == 1
    assert matches[0].keyword == "business funding"


def test_record_keyword_hits_inserts_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "keywords.db"
    migrate(db_path)

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES ('wbap-am-820', 'http://x', 1)"
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

            matches = find_keyword_matches(
                "Need merchant cash advance and business funding today.",
                [
                    LoanKeywordEntry(phrase="merchant cash advance", confidence=0.80),
                    LoanKeywordEntry(phrase="business funding", confidence=0.85),
                ],
            )
            inserted = record_keyword_hits(
                conn,
                station_id=station_id,
                chunk_id=chunk_id,
                hit_ts=1000.0,
                matches=matches,
            )
            assert inserted == 2

        rows = conn.execute(
            "SELECT keyword, station_id, chunk_id, hit_ts, context_excerpt FROM keyword_hits ORDER BY keyword"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["keyword"] == "business funding"
        assert rows[1]["keyword"] == "merchant cash advance"
        assert rows[0]["context_excerpt"].startswith("[confidence=")
        assert rows[0]["station_id"] == station_id
        assert rows[0]["hit_ts"] == pytest.approx(1000.0)
    finally:
        conn.close()


def test_record_keyword_hits_is_idempotent_per_chunk_keyword(tmp_path: Path) -> None:
    db_path = tmp_path / "keywords.db"
    migrate(db_path)

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES ('test-fm', 'http://x', 1)"
            )
            station_id = conn.execute("SELECT id FROM stations").fetchone()[0]
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, 'chunk.wav', 1.0, 91.0, 'done')
                """,
                (station_id,),
            )
            chunk_id = conn.execute("SELECT id FROM chunks").fetchone()[0]
            matches = find_keyword_matches(
                "tax debt relief now",
                [LoanKeywordEntry(phrase="tax debt relief", confidence=0.90)],
            )

            first = record_keyword_hits(
                conn,
                station_id=station_id,
                chunk_id=chunk_id,
                hit_ts=1.0,
                matches=matches,
            )
            second = record_keyword_hits(
                conn,
                station_id=station_id,
                chunk_id=chunk_id,
                hit_ts=1.0,
                matches=matches,
            )
            assert first == 1
            assert second == 0

        count = conn.execute("SELECT COUNT(*) FROM keyword_hits").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_find_keyword_matches_respects_word_boundaries() -> None:
    # "loan" must not match inside "balloon"; "heloc" must not match a larger token.
    assert find_keyword_matches("we sell a balloon today", ["loan"]) == []
    assert find_keyword_matches("the helocopter landed", ["heloc"]) == []
    assert {m.keyword for m in find_keyword_matches("get a personal loan now", ["loan"])} == {"loan"}
    assert {m.keyword for m in find_keyword_matches("apply for a HELOC online", ["heloc"])} == {"heloc"}


def test_find_keyword_matches_tolerates_internal_whitespace() -> None:
    # ASR may emit extra spaces between phrase tokens.
    matches = find_keyword_matches("a cash-out   refinance offer", ["cash-out refinance"])
    assert {m.keyword for m in matches} == {"cash-out refinance"}
