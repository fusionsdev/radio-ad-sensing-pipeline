"""Tests for shared.pipeline_loan_ops."""

from __future__ import annotations

from pathlib import Path

from shared.db import get_connection, migrate
from shared.pipeline_loan_ops import ServiceStatus, build_loan_ops_report


def _seed_station(conn, *, name: str, enabled: int = 1) -> int:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, ?)",
        (name, "https://example.com/live", enabled),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_chunk(conn, *, station_id: int, chunk_id: int, start_ts: float, status: str = "done") -> None:
    conn.execute(
        """
        INSERT INTO chunks (id, station_id, path, start_ts, end_ts, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chunk_id, station_id, f"/app/chunks/test/{chunk_id}.wav", start_ts, start_ts + 90, status),
    )


def test_loan_ops_report_counts_true_loan_only(tmp_path: Path) -> None:
    db = tmp_path / "loan_ops.db"
    migrate(db)
    conn = get_connection(db)
    station_id = _seed_station(conn, name="klif-am-570")
    now = 10_000.0
    _seed_chunk(conn, station_id=station_id, chunk_id=1, start_ts=now - 1800)
    conn.execute(
        "INSERT INTO transcripts (chunk_id, text) VALUES (1, ?)",
        ("Apply for a personal loan today with same day funding.",),
    )
    conn.execute(
        """
        INSERT INTO detections (
            chunk_id, is_ad, ad_category, company_name, offer_summary, key_claims, confidence, alerted
        ) VALUES (1, 1, 'business_funding', 'QuickCash', 'personal loan offer', '', 0.9, 0)
        """,
    )
    conn.execute(
        """
        INSERT INTO detections (
            chunk_id, is_ad, ad_category, company_name, offer_summary, key_claims, confidence, alerted
        ) VALUES (1, 1, 'tax_relief', 'Optima Tax', 'tax relief for IRS debt', '', 0.9, 0)
        """,
    )
    conn.commit()

    report = build_loan_ops_report(
        conn,
        db_path=str(db),
        now_ts=now,
        services=(
            ServiceStatus("ingestor", "up"),
            ServiceStatus("worker", "up"),
            ServiceStatus("alerter", "up"),
            ServiceStatus("dashboard", "up"),
        ),
    )
    conn.close()

    assert report.source_stale is False
    assert "| last 1h | 1 |" in report.markdown
    assert "QuickCash" in report.markdown
    assert "**Action:**" in report.markdown
    assert report.action_needed in {
        "no_action",
        "review_new_loan_candidate",
        "rotate_station",
        "fix_stream",
        "pipeline_problem",
        "source_stale_warning",
    }


def test_loan_ops_report_stale_source_skips_loan_conclusions(tmp_path: Path) -> None:
    db = tmp_path / "stale.db"
    migrate(db)
    conn = get_connection(db)
    report = build_loan_ops_report(conn, db_path=str(db), now_ts=10_000.0)
    conn.close()

    assert report.source_stale is True
    assert "STALE SOURCE WARNING" in report.markdown
    assert report.action_needed == "source_stale_warning"
    assert "| last 1h | — | — | — |" in report.markdown
