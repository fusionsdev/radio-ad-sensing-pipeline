"""Tests for vertical hit classification and report eligibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.db import get_connection, migrate, transaction
from shared.verticals import (
    classify_vertical_hits,
    fetch_vertical_summaries_from_db,
    flatten_vertical_keywords,
    load_vertical_keywords,
)


def test_load_vertical_keywords_has_all_verticals() -> None:
    config = load_vertical_keywords()
    assert set(config.verticals) == {
        "tax_relief",
        "insurance",
        "timeshare_exit",
        "debt_relief",
        "loan",
    }
    assert config.verticals["tax_relief"].tier == "hot"
    assert config.verticals["insurance"].tier == "watchlist"
    assert config.verticals["loan"].no_hit_ok is True


def test_flatten_vertical_keywords_deduplicates() -> None:
    phrases = {entry.phrase.lower() for entry in flatten_vertical_keywords()}
    assert "back taxes" in phrases
    assert "business funding" in phrases
    assert len(phrases) == len(flatten_vertical_keywords())


def test_classify_tax_relief_hot_and_report_eligible() -> None:
    rows = [
        {"keyword": "back taxes", "station_id": 1, "hit_ts": 1_700_000_000.0, "hits": 11},
        {"keyword": "unfiled tax returns", "station_id": 2, "hit_ts": 1_700_000_100.0, "hits": 11},
    ]
    summaries = classify_vertical_hits(rows)
    tax = next(s for s in summaries if s.vertical == "tax_relief")
    assert tax.vertical_hit_count == 22
    assert tax.station_count == 2
    assert tax.report_eligible is True
    assert tax.tier == "hot"
    assert "back taxes" in tax.source_keywords


def test_classify_loan_no_hit_not_failure() -> None:
    rows = [{"keyword": "back taxes", "station_id": 1, "hit_ts": 1.0, "hits": 5}]
    summaries = classify_vertical_hits(rows)
    loan = next(s for s in summaries if s.vertical == "loan")
    assert loan.vertical_hit_count == 0
    assert loan.no_hit_ok is True
    assert loan.report_eligible is False


def test_debt_relief_sparse_not_report_eligible() -> None:
    rows = [{"keyword": "debt relief", "station_id": 1, "hit_ts": 1.0, "hits": 1}]
    summaries = classify_vertical_hits(rows)
    debt = next(s for s in summaries if s.vertical == "debt_relief")
    assert debt.vertical_hit_count == 1
    assert debt.report_eligible is False
    assert debt.confidence <= 0.50


def test_fetch_vertical_summaries_from_db(tmp_path: Path) -> None:
    db_path = tmp_path / "verticals.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES ('klif', 'http://x', 1)"
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
            conn.execute(
                """
                INSERT INTO keyword_hits (
                    station_id, keyword, chunk_id, hit_ts, context_excerpt
                ) VALUES (?, 'tax relief', ?, 100.0, 'excerpt')
                """,
                (station_id, chunk_id),
            )
        summaries = fetch_vertical_summaries_from_db(conn)
        tax = next(s for s in summaries if s.vertical == "tax_relief")
        assert tax.vertical_hit_count == 1
        assert tax.report_eligible is True
    finally:
        conn.close()
