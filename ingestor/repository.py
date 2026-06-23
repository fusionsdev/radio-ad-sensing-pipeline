"""SQLite persistence helpers for the ingestor service."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import ChunkStatus, StationConfig


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


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
def mark_station_recovering(
    db_path: str | Path,
    station_name: str,
) -> None:
    """Mark a runtime-started station as recovering until it produces a valid chunk."""
    now_iso = datetime.now(tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO station_health (
                    station_id, health_state, enabled, consecutive_failures,
                    cool_down_until, last_error, updated_at
                ) VALUES (?, 'recovering', 1, 0, NULL, NULL, ?)
                ON CONFLICT(station_id) DO UPDATE SET
                    health_state = 'recovering',
                    enabled = 1,
                    consecutive_failures = 0,
                    cool_down_until = NULL,
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (station_name, now_iso),
            )
    finally:
        conn.close()


@retry_on_busy()
def mark_station_disabled(
    db_path: str | Path,
    station_name: str,
    *,
    reason: str,
) -> None:
    """Persist a real station disable so runtime state and DB state do not diverge."""
    now_iso = datetime.now(tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute("UPDATE stations SET enabled = 0 WHERE name = ?", (station_name,))
            conn.execute(
                """
                INSERT INTO station_health (
                    station_id, health_state, enabled, last_failure_at,
                    disabled_at, last_error, updated_at
                ) VALUES (?, 'failed', 0, ?, ?, ?, ?)
                ON CONFLICT(station_id) DO UPDATE SET
                    health_state = 'failed',
                    enabled = 0,
                    last_failure_at = excluded.last_failure_at,
                    disabled_at = excluded.disabled_at,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (station_name, now_iso, now_iso, reason, now_iso),
            )
    finally:
        conn.close()


@retry_on_busy()
def upsert_station(
    db_path: str | Path,
    station: StationConfig,
    *,
    sync_enabled: bool = True,
) -> int:
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
                    enabled = CASE
                        WHEN ? THEN excluded.enabled
                        ELSE stations.enabled
                    END,
                    display_name = excluded.display_name
                """,
                (
                    station.name,
                    station.url,
                    station.format,
                    1 if station.enabled else 0,
                    station.display_name,
                    1 if sync_enabled else 0,
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


@retry_on_busy()
def upsert_station_ingest_health(
    db_path: str | Path,
    *,
    station: StationConfig,
    status: str,
    now_ts: float,
    last_success_at: float | None,
    last_failure_at: float | None,
    consecutive_empty_chunks: int,
    consecutive_stream_down: int,
    attempts_since_success: int,
    backoff_until: float | None,
    last_ffmpeg_error_sample: str,
    url_hash: str,
    enabled: bool | None = None,
) -> None:
    """Persist ingestor-owned station health without requiring schema changes."""
    updated_at = _iso(now_ts)
    last_success_iso = _iso(last_success_at)
    last_failure_iso = _iso(last_failure_at)
    backoff_until_iso = _iso(backoff_until)
    consecutive_failures = consecutive_empty_chunks + consecutive_stream_down
    enabled_value = station.enabled if enabled is None else enabled
    last_error = None if status == "healthy" else last_ffmpeg_error_sample
    health_payload = {
        "status": status,
        "last_success_at": last_success_at,
        "last_failure_at": last_failure_at,
        "consecutive_empty_chunks": consecutive_empty_chunks,
        "consecutive_stream_down": consecutive_stream_down,
        "attempts_since_success": attempts_since_success,
        "backoff_until": backoff_until,
        "last_ffmpeg_error_sample": last_ffmpeg_error_sample,
        "url_hash": url_hash,
    }
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO station_health (
                    station_id, health_state, enabled, last_chunk_at,
                    last_success_at, last_failure_at, consecutive_failures,
                    restart_count_today, cool_down_until, last_error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_id) DO UPDATE SET
                    health_state = excluded.health_state,
                    enabled = excluded.enabled,
                    last_chunk_at = COALESCE(excluded.last_chunk_at, station_health.last_chunk_at),
                    last_success_at = COALESCE(
                        excluded.last_success_at,
                        station_health.last_success_at
                    ),
                    last_failure_at = COALESCE(
                        excluded.last_failure_at,
                        station_health.last_failure_at
                    ),
                    consecutive_failures = excluded.consecutive_failures,
                    restart_count_today = CASE
                        WHEN excluded.health_state = 'healthy' THEN 0
                        ELSE station_health.restart_count_today
                    END,
                    cool_down_until = excluded.cool_down_until,
                    last_error = excluded.last_error,
                    disabled_at = CASE
                        WHEN excluded.health_state = 'healthy' THEN NULL
                        ELSE station_health.disabled_at
                    END,
                    updated_at = excluded.updated_at
                """,
                (
                    station.name,
                    status,
                    1 if enabled_value else 0,
                    last_success_iso,
                    last_success_iso,
                    last_failure_iso,
                    consecutive_failures,
                    0,
                    backoff_until_iso,
                    last_error,
                    updated_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO status (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    f"ingestor:station_health:{station.name}",
                    json.dumps(health_payload, sort_keys=True),
                    now_ts,
                ),
            )
    finally:
        conn.close()


def fetch_station(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    """Return a station row by name. Intended for diagnostics/tests."""
    return conn.execute("SELECT * FROM stations WHERE name = ?", (name,)).fetchone()
