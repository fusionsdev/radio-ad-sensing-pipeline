"""Watchdog auto-recovery: restart stale stations via control commands."""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import WatchdogSettings
from shared.station_control import (
    CommandStatus,
    StationControlCommand,
    enqueue_station_command,
    has_active_command,
    has_pending_command,
    log_recovery_event,
)
from watchdog.health import StationHealthSnapshot


def _utc_today() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def _parse_iso_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.timestamp()
    except ValueError:
        return None


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


def _restart_day_key(station_id: str) -> str:
    return f"watchdog:restart_day:{station_id}"


def _restart_marker_key(station_id: str) -> str:
    return f"watchdog:restart_attempt:{station_id}"


def _outage_marker(snap: StationHealthSnapshot) -> str:
    return f"{snap.last_chunk_ts or 0:.3f}"


def _fetch_health_row(conn: sqlite3.Connection, station_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT health_state, restart_count_today, consecutive_failures, cool_down_until
        FROM station_health
        WHERE station_id = ?
        """,
        (station_id,),
    ).fetchone()


def _fixed_harvest_observe_only(settings: WatchdogSettings) -> bool:
    return settings.fixed_harvest_mode and not settings.fixed_harvest_auto_restart_enabled


@retry_on_busy()
def _reset_daily_restart_count_if_needed(
    db_path: str | Path,
    station_id: str,
) -> int:
    today = _utc_today()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            marker = _get_status_value(conn, _restart_day_key(station_id))
            row = _fetch_health_row(conn, station_id)
            count = int(row["restart_count_today"] or 0) if row is not None else 0
            if marker != today:
                count = 0
                conn.execute(
                    """
                    UPDATE station_health
                    SET restart_count_today = 0, updated_at = ?
                    WHERE station_id = ?
                    """,
                    (datetime.now(tz=UTC).isoformat(), station_id),
                )
                _set_status_value(conn, _restart_day_key(station_id), today)
            return count
    finally:
        conn.close()


def is_in_cooldown(db_path: str | Path, station_id: str, *, now_ts: float) -> bool:
    conn = get_connection(db_path, read_only=True)
    try:
        row = _fetch_health_row(conn, station_id)
        if row is None:
            return False
        cool_down_until = _parse_iso_ts(row["cool_down_until"])
        return cool_down_until is not None and now_ts < cool_down_until
    finally:
        conn.close()


def _latest_chunk_ts(conn: sqlite3.Connection, station_id: str) -> float | None:
    row = conn.execute(
        """
        SELECT MAX(c.end_ts) AS last_chunk_ts
        FROM stations s
        LEFT JOIN chunks c ON c.station_id = s.id
        WHERE s.name = ?
        """,
        (station_id,),
    ).fetchone()
    if row is None or row["last_chunk_ts"] is None:
        return None
    return float(row["last_chunk_ts"])


def _has_fresh_chunk(
    db_path: str | Path,
    station_id: str,
    *,
    settings: WatchdogSettings,
    now_ts: float,
) -> bool:
    conn = get_connection(db_path, read_only=True)
    try:
        last_chunk_ts = _latest_chunk_ts(conn, station_id)
    finally:
        conn.close()
    if last_chunk_ts is None:
        return False
    stale_after_seconds = settings.station_stale_after_minutes * 60
    return max(now_ts - last_chunk_ts, 0.0) < stale_after_seconds


def _latest_recovery_command_ts(
    conn: sqlite3.Connection,
    station_id: str,
) -> float | None:
    row = conn.execute(
        """
        SELECT created_at, processed_at
        FROM station_control_commands
        WHERE station_id = ?
          AND command IN (?, ?)
          AND status IN (?, ?, ?)
        ORDER BY COALESCE(processed_at, created_at) DESC, id DESC
        LIMIT 1
        """,
        (
            station_id,
            StationControlCommand.ENABLE.value,
            StationControlCommand.RESTART.value,
            CommandStatus.PENDING.value,
            CommandStatus.PROCESSING.value,
            CommandStatus.DONE.value,
        ),
    ).fetchone()
    if row is None:
        return None
    return _parse_iso_ts(row["processed_at"]) or _parse_iso_ts(row["created_at"])


def _is_in_manual_recovery_grace(
    db_path: str | Path,
    station_id: str,
    *,
    settings: WatchdogSettings,
    now_ts: float,
) -> bool:
    grace_seconds = max(settings.manual_recovery_grace_minutes, 0) * 60
    if grace_seconds <= 0:
        return False
    conn = get_connection(db_path, read_only=True)
    try:
        command_ts = _latest_recovery_command_ts(conn, station_id)
    finally:
        conn.close()
    if command_ts is None:
        return False
    return 0 <= now_ts - command_ts < grace_seconds


def _restart_already_attempted(
    db_path: str | Path,
    snap: StationHealthSnapshot,
) -> bool:
    conn = get_connection(db_path, read_only=True)
    try:
        marker = _get_status_value(conn, _restart_marker_key(snap.station_id))
    finally:
        conn.close()
    return marker == _outage_marker(snap)


def _manual_attention_reason_if_budget_exhausted(
    db_path: str | Path,
    station_id: str,
    *,
    settings: WatchdogSettings,
) -> str | None:
    restart_count_today = _reset_daily_restart_count_if_needed(db_path, station_id)
    conn = get_connection(db_path, read_only=True)
    try:
        row = _fetch_health_row(conn, station_id)
        consecutive = int(row["consecutive_failures"] or 0) if row is not None else 0
    finally:
        conn.close()

    if consecutive >= settings.restart_attempts_before_disable:
        return f"consecutive stale episodes ({consecutive}) reached limit"
    if restart_count_today >= settings.max_station_failures_per_day:
        return f"daily restart limit ({settings.max_station_failures_per_day}) reached"
    return None


@retry_on_busy()
def _mark_restart_attempted(
    db_path: str | Path,
    snap: StationHealthSnapshot,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            _set_status_value(conn, _restart_marker_key(snap.station_id), _outage_marker(snap))
    finally:
        conn.close()


@retry_on_busy()
def disable_stale_station(
    db_path: str | Path,
    snap: StationHealthSnapshot,
    *,
    settings: WatchdogSettings,
    now_ts: float,
    reason: str,
) -> None:
    cool_down_until = datetime.fromtimestamp(
        now_ts + settings.cool_down_minutes_after_failure * 60,
        tz=UTC,
    ).isoformat()
    disabled_at = datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            row = _fetch_health_row(conn, snap.station_id)
            old_state = row["health_state"] if row is not None else "stale"
            conn.execute(
                "UPDATE stations SET enabled = 0 WHERE name = ?",
                (snap.station_id,),
            )
            conn.execute(
                """
                UPDATE station_health
                SET health_state = 'failed',
                    enabled = 0,
                    disabled_at = ?,
                    cool_down_until = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE station_id = ?
                """,
                (disabled_at, cool_down_until, reason, disabled_at, snap.station_id),
            )
    finally:
        conn.close()
    log_recovery_event(
        db_path,
        station_id=snap.station_id,
        event_type="station_disabled",
        old_state=old_state,
        new_state="failed",
        reason=reason,
        action_taken="disable_station",
    )
    if not has_pending_command(
        db_path,
        station_id=snap.station_id,
        command=StationControlCommand.DISABLE,
    ):
        enqueue_station_command(
            db_path,
            station_id=snap.station_id,
            command=StationControlCommand.DISABLE,
            reason=reason,
        )


@retry_on_busy()
def mark_manual_attention_needed(
    db_path: str | Path,
    snap: StationHealthSnapshot,
    *,
    reason: str,
) -> None:
    now_iso = datetime.now(tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            row = _fetch_health_row(conn, snap.station_id)
            old_state = row["health_state"] if row is not None else "stale"
            conn.execute(
                """
                INSERT INTO station_health (
                    station_id, health_state, enabled, last_error, updated_at
                ) VALUES (?, 'manual_attention', 1, ?, ?)
                ON CONFLICT(station_id) DO UPDATE SET
                    health_state = 'manual_attention',
                    enabled = 1,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (snap.station_id, reason, now_iso),
            )
            conn.execute(
                """
                INSERT INTO station_recovery_events (
                    station_id, event_type, old_state, new_state, reason, action_taken
                ) VALUES (?, 'manual_attention_needed', ?, 'manual_attention', ?, 'observe_only')
                """,
                (snap.station_id, old_state, reason),
            )
    finally:
        conn.close()


@retry_on_busy()
def _increment_consecutive_failures(db_path: str | Path, station_id: str) -> int:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            row = _fetch_health_row(conn, station_id)
            current = int(row["consecutive_failures"] or 0) if row is not None else 0
            new_value = current + 1
            conn.execute(
                """
                UPDATE station_health
                SET consecutive_failures = ?, updated_at = ?
                WHERE station_id = ?
                """,
                (new_value, datetime.now(tz=UTC).isoformat(), station_id),
            )
            return new_value
    finally:
        conn.close()


@retry_on_busy()
def _mark_recovering(db_path: str | Path, station_id: str, *, restart_count_today: int) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                UPDATE station_health
                SET health_state = 'recovering',
                    restart_count_today = ?,
                    updated_at = ?
                WHERE station_id = ?
                """,
                (restart_count_today, datetime.now(tz=UTC).isoformat(), station_id),
            )
            _set_status_value(conn, _restart_day_key(station_id), _utc_today())
    finally:
        conn.close()


def auto_restart_stale_station(
    db_path: str | Path,
    snap: StationHealthSnapshot,
    *,
    settings: WatchdogSettings,
    now_ts: float,
) -> str | None:
    """Queue restart or disable for a new stale episode. Returns action label."""
    if not settings.auto_restart_on_stale:
        return None
    if not snap.enabled or not snap.is_stale:
        return None
    if _has_fresh_chunk(db_path, snap.station_id, settings=settings, now_ts=now_ts):
        return "fresh_skip"
    if has_active_command(db_path, station_id=snap.station_id):
        return "command_pending"
    if _is_in_manual_recovery_grace(
        db_path,
        snap.station_id,
        settings=settings,
        now_ts=now_ts,
    ):
        return "manual_grace_skip"
    if is_in_cooldown(db_path, snap.station_id, now_ts=now_ts):
        return "cooldown_skip"
    if _restart_already_attempted(db_path, snap):
        return "restart_already_attempted"
    if _fixed_harvest_observe_only(settings):
        reason = _manual_attention_reason_if_budget_exhausted(
            db_path,
            snap.station_id,
            settings=settings,
        )
        if reason is not None:
            mark_manual_attention_needed(db_path, snap, reason=reason)
            _mark_restart_attempted(db_path, snap)
            return "manual_attention"
        _mark_restart_attempted(db_path, snap)
        return "fixed_harvest_observe_only"

    restart_count_today = _reset_daily_restart_count_if_needed(db_path, snap.station_id)
    consecutive = _increment_consecutive_failures(db_path, snap.station_id)

    if consecutive >= settings.restart_attempts_before_disable:
        if settings.fixed_harvest_mode:
            mark_manual_attention_needed(
                db_path,
                snap,
                reason=f"consecutive stale episodes ({consecutive}) reached limit",
            )
            _mark_restart_attempted(db_path, snap)
            return "manual_attention"
        disable_stale_station(
            db_path,
            snap,
            settings=settings,
            now_ts=now_ts,
            reason=f"consecutive stale episodes ({consecutive}) reached limit",
        )
        _mark_restart_attempted(db_path, snap)
        return "disabled"

    if restart_count_today >= settings.max_station_failures_per_day:
        if settings.fixed_harvest_mode:
            mark_manual_attention_needed(
                db_path,
                snap,
                reason=f"daily restart limit ({settings.max_station_failures_per_day}) reached",
            )
            _mark_restart_attempted(db_path, snap)
            return "manual_attention"
        disable_stale_station(
            db_path,
            snap,
            settings=settings,
            now_ts=now_ts,
            reason=f"daily restart limit ({settings.max_station_failures_per_day}) reached",
        )
        _mark_restart_attempted(db_path, snap)
        return "disabled"

    if has_pending_command(
        db_path,
        station_id=snap.station_id,
        command=StationControlCommand.RESTART,
    ):
        return "restart_pending"

    attempt_number = restart_count_today + 1
    enqueue_station_command(
        db_path,
        station_id=snap.station_id,
        command=StationControlCommand.RESTART,
        reason=f"watchdog auto-restart attempt {attempt_number}/{settings.restart_attempts_before_disable}",
    )
    _mark_recovering(db_path, snap.station_id, restart_count_today=attempt_number)
    _mark_restart_attempted(db_path, snap)
    log_recovery_event(
        db_path,
        station_id=snap.station_id,
        event_type="restart_attempted",
        old_state="stale",
        new_state="recovering",
        reason=f"stale for {int((snap.age_seconds or 0) // 60)} minutes",
        action_taken="restart_station",
    )
    return "restart_queued"
