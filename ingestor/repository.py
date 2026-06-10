"""SQLite persistence helpers for the ingestor service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import ChunkStatus, StationConfig


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
