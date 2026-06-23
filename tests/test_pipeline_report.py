"""Tests for shared.pipeline_report."""

from __future__ import annotations

from pathlib import Path

from shared.db import get_connection, migrate
from shared.pipeline_report import build_pipeline_report_snapshot


def _seed_station(conn, *, name: str, enabled: int = 1) -> int:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, ?)",
        (name, "https://example.com/live", enabled),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def test_pipeline_report_snapshot_includes_keywords(tmp_path: Path) -> None:
    db = tmp_path / "report.db"
    migrate(db)
    conn = get_connection(db)
    station_id = _seed_station(conn, name="klif-am-570")
    conn.execute(
        """
        INSERT INTO keyword_hits (station_id, keyword, chunk_id, hit_ts)
        VALUES (?, 'personal loan', 1, 2000.0)
        """,
        (station_id,),
    )
    conn.commit()
    snapshot = build_pipeline_report_snapshot(
        conn,
        now_ts=3000.0,
        since_ts=1000.0,
        interval_hours=3.0,
    )
    conn.close()
    text = snapshot.format_telegram()
    assert "consumer_personal_loan_v1" in text
    assert "keyword_hits total: 1" in text
    assert "personal loan×1" in text or "personal loan" in text
    assert "klif-am-570" in text
