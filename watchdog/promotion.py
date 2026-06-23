"""Queue-gated promotion of backup stations from the replacement pool."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from shared.db import get_connection, retry_on_busy
from shared.models import WatchdogSettings
from shared.station_control import CommandStatus, StationControlCommand
from watchdog.notify import QueueSnapshot
from watchdog.pool import count_active_stations, select_backup_candidate


def _promote_hour_key(now_ts: float) -> str:
    hour = datetime.fromtimestamp(now_ts, tz=UTC).strftime("%Y%m%d%H")
    return f"watchdog:promote_hour:{hour}"


def _get_status_value(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM status WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else None


def _set_status_value(conn, key: str, value: str) -> None:
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


def _promotions_this_hour(db_path: str | Path, *, now_ts: float) -> int:
    conn = get_connection(db_path, read_only=True)
    try:
        value = _get_status_value(conn, _promote_hour_key(now_ts))
        return int(value) if value is not None else 0
    finally:
        conn.close()


@retry_on_busy()
def _record_promotion(
    db_path: str | Path,
    *,
    station_id: str,
    reason: str,
    now_ts: float,
) -> bool:
    promoted_at = datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            eligible = conn.execute(
                """
                SELECT 1
                FROM station_pool p
                JOIN stations s ON s.name = p.station_id
                LEFT JOIN station_health h ON h.station_id = p.station_id
                WHERE p.station_id = ?
                  AND p.replacement_eligible = 1
                  AND s.enabled = 0
                  AND p.needs_stream_resolution = 0
                  AND COALESCE(p.stream_validation_status, '') NOT IN ('fail', 'banned')
                  AND COALESCE(h.health_state, 'unknown') NOT IN ('banned', 'permanently_failed')
                  AND (
                        h.cool_down_until IS NULL
                        OR h.cool_down_until <= ?
                      )
                LIMIT 1
                """,
                (station_id, promoted_at),
            ).fetchone()
            if eligible is None:
                conn.rollback()
                return False

            active_command = conn.execute(
                """
                SELECT 1
                FROM station_control_commands
                WHERE station_id = ?
                  AND status IN (?, ?)
                LIMIT 1
                """,
                (station_id, CommandStatus.PENDING.value, CommandStatus.PROCESSING.value),
            ).fetchone()
            if active_command is not None:
                conn.rollback()
                return False

            conn.execute(
                "UPDATE stations SET enabled = 1 WHERE name = ?",
                (station_id,),
            )
            conn.execute(
                """
                INSERT INTO station_health (
                    station_id, health_state, enabled, promoted_at, consecutive_failures,
                    cool_down_until, updated_at
                ) VALUES (?, 'recovering', 1, ?, 0, NULL, ?)
                ON CONFLICT(station_id) DO UPDATE SET
                    health_state = 'recovering',
                    enabled = 1,
                    promoted_at = excluded.promoted_at,
                    consecutive_failures = 0,
                    cool_down_until = NULL,
                    updated_at = excluded.updated_at
                """,
                (station_id, promoted_at, promoted_at),
            )
            key = _promote_hour_key(now_ts)
            current = int(_get_status_value(conn, key) or 0)
            _set_status_value(conn, key, str(current + 1))
            conn.execute(
                """
                INSERT INTO station_control_commands (station_id, command, status, reason)
                VALUES (?, ?, ?, ?)
                """,
                (
                    station_id,
                    StationControlCommand.PROMOTE.value,
                    CommandStatus.PENDING.value,
                    reason,
                ),
            )
            conn.execute(
                """
                INSERT INTO station_recovery_events (
                    station_id, event_type, old_state, new_state, reason, action_taken
                ) VALUES (?, 'station_promoted', 'standby', 'recovering', ?, 'promote_station')
                """,
                (station_id, reason),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


def maybe_promote_backup(
    db_path: str | Path,
    *,
    settings: WatchdogSettings,
    queue: QueueSnapshot,
    now_ts: float | None = None,
) -> str | None:
    """Promote one backup when safe. Returns action label or None when skipped."""
    if settings.fixed_harvest_mode:
        return "promotion_blocked_fixed_harvest"

    if not settings.auto_promotion_enabled:
        return None

    if not settings.promote_backup_when_active_below_target:
        return None

    now_ts = now_ts if now_ts is not None else time.time()
    active_count = count_active_stations(db_path)
    if active_count >= settings.target_active_stations:
        return None

    if queue.level == "critical":
        return "promotion_blocked_queue"

    if _promotions_this_hour(db_path, now_ts=now_ts) >= settings.max_promotions_per_hour:
        return "promotion_rate_limited"

    candidate = select_backup_candidate(db_path, settings=settings, now_ts=now_ts)
    if candidate is None:
        return "pool_empty"

    station_id = str(candidate["station_id"])
    if _has_active_command(db_path, station_id=station_id):
        return "promotion_pending"

    reason = (
        f"auto-promote backup (active {active_count}/{settings.target_active_stations}, "
        f"queue {queue.level})"
    )
    if not _record_promotion(
        db_path,
        station_id=station_id,
        reason=reason,
        now_ts=now_ts,
    ):
        return "promotion_pending"
    return "promoted"


def _has_active_command(db_path: str | Path, *, station_id: str) -> bool:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM station_control_commands
            WHERE station_id = ?
              AND status IN (?, ?)
            LIMIT 1
            """,
            (station_id, CommandStatus.PENDING.value, CommandStatus.PROCESSING.value),
        ).fetchone()
        return row is not None
    finally:
        conn.close()
