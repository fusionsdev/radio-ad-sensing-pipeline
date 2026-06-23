"""SQLite persistence for station health and recovery events."""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from watchdog.health import StationHealthSnapshot


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


@retry_on_busy()
def sync_station_health(
    db_path: str | Path,
    snapshots: list[StationHealthSnapshot],
) -> None:
    """Upsert station_health rows from current snapshots."""
    now_iso = datetime.now(tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            for snap in snapshots:
                conn.execute(
                    """
                    INSERT INTO station_health (
                        station_id, health_state, enabled, last_chunk_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(station_id) DO UPDATE SET
                        health_state = excluded.health_state,
                        enabled = excluded.enabled,
                        last_chunk_at = excluded.last_chunk_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        snap.station_id,
                        snap.health_state,
                        1 if snap.enabled else 0,
                        _iso(snap.last_chunk_ts),
                        now_iso,
                    ),
                )
                if snap.health_state == "healthy":
                    conn.execute(
                        """
                        UPDATE station_health
                        SET consecutive_failures = 0,
                            restart_count_today = 0,
                            cool_down_until = NULL,
                            last_error = NULL,
                            disabled_at = NULL
                        WHERE station_id = ?
                        """,
                        (snap.station_id,),
                    )
    finally:
        conn.close()


def _alert_marker_key(station_id: str) -> str:
    return f"watchdog:stale_alert:{station_id}"


def _restart_marker_key(station_id: str) -> str:
    return f"watchdog:restart_attempt:{station_id}"


def _get_status_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM status WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else None


def _set_status_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO status (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, time.time()),
    )


@retry_on_busy()
def record_stale_detection(
    db_path: str | Path,
    snap: StationHealthSnapshot,
    *,
    now_ts: float,
) -> bool:
    """Log stale_detected once per outage episode. Returns True when newly logged."""
    marker = _alert_marker_key(snap.station_id)
    outage_marker = f"{snap.last_chunk_ts or 0:.3f}"
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            previous = _get_status_value(conn, marker)
            if previous == outage_marker:
                return False
            row = conn.execute(
                "SELECT health_state FROM station_health WHERE station_id = ?",
                (snap.station_id,),
            ).fetchone()
            old_state = row["health_state"] if row is not None else "unknown"
            conn.execute(
                """
                INSERT INTO station_recovery_events (
                    station_id, event_type, old_state, new_state, reason, action_taken
                ) VALUES (?, 'stale_detected', ?, 'stale', ?, 'observe_only')
                """,
                (
                    snap.station_id,
                    old_state,
                    _stale_reason(snap, now_ts),
                ),
            )
            _set_status_value(conn, marker, outage_marker)
    finally:
        conn.close()
    return True


def clear_stale_alert_marker(db_path: str | Path, station_id: str) -> None:
    """Clear stale/recovery markers when station becomes healthy again."""
    marker = _alert_marker_key(station_id)
    restart_marker = _restart_marker_key(station_id)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute("DELETE FROM status WHERE key IN (?, ?)", (marker, restart_marker))
    finally:
        conn.close()


def _stale_reason(snap: StationHealthSnapshot, now_ts: float) -> str:
    if snap.last_chunk_ts is None:
        return "no chunks recorded"
    minutes = int(max(now_ts - snap.last_chunk_ts, 0) // 60)
    return f"no chunk for {minutes} minutes"


def fetch_recent_recovery_events(db_path: str | Path, *, limit: int = 50) -> list[dict]:
    conn = get_connection(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT id, station_id, event_type, old_state, new_state,
                   reason, action_taken, replacement_station_id, created_at
            FROM station_recovery_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
