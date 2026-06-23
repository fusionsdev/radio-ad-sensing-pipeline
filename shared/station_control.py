"""Station control command queue (watchdog / dashboard → ingestor)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction


class StationControlCommand(str, Enum):
    RESTART = "restart_station"
    DISABLE = "disable_station"
    ENABLE = "enable_station"
    PROMOTE = "promote_station"


class CommandStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


@retry_on_busy()
def enqueue_station_command(
    db_path: str | Path,
    *,
    station_id: str,
    command: StationControlCommand | str,
    reason: str | None = None,
) -> int:
    command_value = command.value if isinstance(command, StationControlCommand) else str(command)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO station_control_commands (station_id, command, status, reason)
                VALUES (?, ?, ?, ?)
                """,
                (station_id, command_value, CommandStatus.PENDING.value, reason),
            )
            return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        conn.close()


def fetch_pending_commands(
    db_path: str | Path,
    *,
    limit: int = 20,
) -> list[dict]:
    conn = get_connection(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT id, station_id, command, status, reason, created_at, processed_at
            FROM station_control_commands
            WHERE status = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (CommandStatus.PENDING.value, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@retry_on_busy()
def mark_command_status(
    db_path: str | Path,
    command_id: int,
    status: CommandStatus,
    *,
    reason: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                UPDATE station_control_commands
                SET status = ?, reason = COALESCE(?, reason), processed_at = ?
                WHERE id = ?
                """,
                (status.value, reason, _now_iso(), command_id),
            )
    finally:
        conn.close()


def station_exists(db_path: str | Path, station_id: str) -> bool:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            "SELECT 1 FROM stations WHERE name = ? LIMIT 1",
            (station_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def has_pending_command(
    db_path: str | Path,
    *,
    station_id: str,
    command: StationControlCommand | str,
    statuses: tuple[CommandStatus | str, ...] = (
        CommandStatus.PENDING,
        CommandStatus.PROCESSING,
    ),
) -> bool:
    command_value = command.value if isinstance(command, StationControlCommand) else str(command)
    status_values = [
        status.value if isinstance(status, CommandStatus) else str(status) for status in statuses
    ]
    if not status_values:
        return False
    placeholders = ", ".join("?" for _ in status_values)
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            f"""
            SELECT 1 FROM station_control_commands
            WHERE station_id = ? AND command = ? AND status IN ({placeholders})
            LIMIT 1
            """,
            (station_id, command_value, *status_values),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def has_active_command(db_path: str | Path, *, station_id: str) -> bool:
    """Return true when any command for a station is pending or processing."""
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT 1 FROM station_control_commands
            WHERE station_id = ?
              AND status IN (?, ?)
            LIMIT 1
            """,
            (station_id, CommandStatus.PENDING.value, CommandStatus.PROCESSING.value),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def control_commands_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='station_control_commands'"
    ).fetchone()
    return row is not None


@retry_on_busy()
def log_recovery_event(
    db_path: str | Path,
    *,
    station_id: str,
    event_type: str,
    old_state: str | None,
    new_state: str | None,
    reason: str | None = None,
    action_taken: str | None = None,
    replacement_station_id: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO station_recovery_events (
                    station_id, event_type, old_state, new_state, reason,
                    action_taken, replacement_station_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    station_id,
                    event_type,
                    old_state,
                    new_state,
                    reason,
                    action_taken,
                    replacement_station_id,
                ),
            )
    finally:
        conn.close()
