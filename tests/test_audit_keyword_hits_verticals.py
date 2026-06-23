"""Tests for legacy keyword_hits audit script."""

from __future__ import annotations

from pathlib import Path

from shared.db import get_connection, migrate, transaction
from shared.keyword_hits_audit import (
    apply_keyword_hits_cleanup,
    audit_keyword_hits,
)


def _insert_hit(conn, *, station_id: int, chunk_id: int, keyword: str) -> None:
    conn.execute(
        """
        INSERT INTO keyword_hits (
            station_id, keyword, chunk_id, hit_ts, context_excerpt
        ) VALUES (?, ?, ?, 100.0, 'excerpt')
        """,
        (station_id, keyword, chunk_id),
    )


def _seed_station_chunk(conn, name: str = "test-fm") -> tuple[int, int]:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, 'http://x', 1)",
        (name,),
    )
    station_id = conn.execute("SELECT id FROM stations").fetchone()[0]
    conn.execute(
        """
        INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
        VALUES (?, 'c.wav', 1.0, 91.0, 'done')
        """,
        (station_id,),
    )
    chunk_id = conn.execute("SELECT id FROM chunks").fetchone()[0]
    return station_id, chunk_id


def test_audit_flags_polluted_legacy_keywords(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id, chunk_id = _seed_station_chunk(conn)
            _insert_hit(conn, station_id=station_id, chunk_id=chunk_id, keyword="back taxes")
            _insert_hit(conn, station_id=station_id, chunk_id=chunk_id, keyword="term life insurance")
            _insert_hit(conn, station_id=station_id, chunk_id=chunk_id, keyword="personal loan")

        report = audit_keyword_hits(conn)
        assert report.total_rows == 3
        flagged = {row.keyword: row.flags for row in report.polluted_keywords}
        assert "back taxes" in flagged
        assert "term life insurance" in flagged
        assert "personal loan" not in flagged
        assert report.clean_consumer_loan_count == 1
    finally:
        conn.close()


def test_dry_run_cleanup_does_not_modify_db(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id, chunk_id = _seed_station_chunk(conn)
            _insert_hit(conn, station_id=station_id, chunk_id=chunk_id, keyword="business funding")

        report = audit_keyword_hits(conn)
        _, messages = apply_keyword_hits_cleanup(conn, report, apply=False)
        assert any("DRY RUN" in msg for msg in messages)
        count = conn.execute("SELECT COUNT(*) FROM keyword_hits").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_apply_deletes_polluted_rows_only(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id, chunk_id = _seed_station_chunk(conn, name="fm-a")
            _insert_hit(conn, station_id=station_id, chunk_id=chunk_id, keyword="debt relief")
            _insert_hit(conn, station_id=station_id, chunk_id=chunk_id, keyword="installment loan")

        report = audit_keyword_hits(conn)
        with transaction(conn):
            deleted, messages = apply_keyword_hits_cleanup(conn, report, apply=True)
        assert deleted == 1
        assert any("APPLIED" in msg for msg in messages)
        remaining = conn.execute(
            "SELECT keyword FROM keyword_hits ORDER BY keyword"
        ).fetchall()
        assert [row["keyword"] for row in remaining] == ["installment loan"]
    finally:
        conn.close()


def test_consumer_personal_loan_target_not_flagged_without_pollution(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "audit.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id, chunk_id = _seed_station_chunk(conn)
            for keyword in ("payday loan", "cash advance", "loan matching"):
                _insert_hit(
                    conn,
                    station_id=station_id,
                    chunk_id=chunk_id,
                    keyword=keyword,
                )

        report = audit_keyword_hits(conn)
        assert report.polluted_row_count == 0
        assert report.clean_consumer_loan_count == 3
    finally:
        conn.close()
