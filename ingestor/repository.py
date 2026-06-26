"""SQLite persistence helpers for the ingestor service."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import ChunkStatus, PipelineSettings, StationConfig

logger = logging.getLogger("ingestor.repository")


def fetch_station_config(db_path: str | Path, station_name: str) -> StationConfig | None:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT name, url, format, enabled, display_name
            FROM stations
            WHERE name = ?
            """,
            (station_name,),
        ).fetchone()
        if row is None:
            return None
        return StationConfig(
            name=str(row["name"]),
            url=str(row["url"]),
            format=row["format"],
            enabled=bool(row["enabled"]),
            display_name=row["display_name"],
        )
    finally:
        conn.close()


def is_station_enabled(db_path: str | Path, station_name: str) -> bool:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            "SELECT enabled FROM stations WHERE name = ?",
            (station_name,),
        ).fetchone()
        if row is None:
            return True
        return bool(row["enabled"])
    finally:
        conn.close()


@retry_on_busy()
def upsert_station(db_path: str | Path, station: StationConfig) -> int:
    """Insert or update a station row and return its id."""
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO stations (name, url, format, enabled, display_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    url = excluded.url,
                    format = excluded.format,
                    enabled = excluded.enabled,
                    display_name = excluded.display_name
                """,
                (
                    station.name,
                    station.url,
                    station.format,
                    1 if station.enabled else 0,
                    station.display_name,
                ),
            )
            row = conn.execute(
                "SELECT id FROM stations WHERE name = ?",
                (station.name,),
            ).fetchone()
            if row is None:  # pragma: no cover - defensive DB invariant
                raise RuntimeError(f"station upsert did not return an id: {station.name}")
            return int(row["id"])
    finally:
        conn.close()


@retry_on_busy()
def enqueue_chunk(
    db_path: str | Path,
    *,
    station_id: int,
    path: str,
    start_ts: float,
    end_ts: float,
) -> int:
    """Create a pending chunk row and return its id."""
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (station_id, path, start_ts, end_ts, ChunkStatus.PENDING.value),
            )
            return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        conn.close()


@retry_on_busy()
def enforce_pending_backlog_limit(db_path: str | Path, settings: PipelineSettings) -> int:
    """Drop oldest pending chunks above the configured queue cap and delete WAVs.

    The worker normally enforces this before claiming work, but if the worker is
    stalled the ingestor can fill the shared chunk tmpfs before that code runs.
    Running the same cap here keeps live ingest writable while preserving the
    newest pending audio.
    """
    max_seconds = settings.queue_max_hours * 3600
    conn = get_connection(db_path)
    drop_rows: list[sqlite3.Row] = []
    try:
        rows = conn.execute(
            """
            SELECT id, station_id, path, start_ts, end_ts
            FROM chunks
            WHERE status = ?
            ORDER BY start_ts ASC
            """,
            (ChunkStatus.PENDING.value,),
        ).fetchall()
        total_duration = sum(row["end_ts"] - row["start_ts"] for row in rows)
        if total_duration <= max_seconds:
            return 0

        overflow_seconds = total_duration - max_seconds
        accumulated = 0.0
        for row in rows:
            drop_rows.append(row)
            accumulated += row["end_ts"] - row["start_ts"]
            if accumulated >= overflow_seconds:
                break

        drop_ids = [row["id"] for row in drop_rows]
        placeholders = ",".join("?" * len(drop_ids))
        with transaction(conn):
            conn.execute(
                f"""
                UPDATE chunks
                SET status = ?, error = ?
                WHERE id IN ({placeholders})
                """,
                (ChunkStatus.DROPPED.value, "dropped_backlog", *drop_ids),
            )
            for row in drop_rows:
                conn.execute(
                    """
                    INSERT INTO gaps (station_id, start_ts, end_ts, reason)
                    VALUES (?, ?, ?, 'dropped_backlog')
                    """,
                    (row["station_id"], row["start_ts"], row["end_ts"]),
                )
    finally:
        conn.close()

    removed = 0
    for row in drop_rows:
        path = Path(row["path"])
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            logger.warning(
                "failed to delete dropped backlog chunk file",
                extra={"chunk_id": row["id"], "path": row["path"]},
                exc_info=True,
            )

    logger.warning(
        "ingestor dropped backlog overflow",
        extra={
            "dropped_count": len(drop_rows),
            "files_deleted": removed,
            "overflow_seconds": overflow_seconds,
        },
    )
    return len(drop_rows)


@retry_on_busy()
def log_gap(
    db_path: str | Path,
    *,
    station_id: int,
    start_ts: float,
    end_ts: float,
    reason: str,
) -> int:
    """Persist an ingestion gap such as stream_down or missing chunk output."""
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO gaps (station_id, start_ts, end_ts, reason)
                VALUES (?, ?, ?, ?)
                """,
                (station_id, start_ts, end_ts, reason),
            )
            return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        conn.close()


def fetch_station(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    """Return a station row by name. Intended for diagnostics/tests."""
    return conn.execute("SELECT * FROM stations WHERE name = ?", (name,)).fetchone()
