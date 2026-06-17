"""Queue-gated promotion of backup stations from the replacement pool."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import WatchdogSettings
from shared.station_control import (
    StationControlCommand,
    enqueue_station_command,
    has_pending_command,
    log_recovery_event,
)
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
def _record_promotion(db_path: str | Path, *, station_id: str, now_ts: float) -> None:
    promoted_at = datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
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
    if has_pending_command(
        db_path,
        station_id=station_id,
        command=StationControlCommand.ENABLE,
    ) or has_pending_command(
        db_path,
        station_id=station_id,
        command=StationControlCommand.PROMOTE,
    ):
        return "promotion_pending"

    reason = (
        f"auto-promote backup (active {active_count}/{settings.target_active_stations}, "
        f"queue {queue.level})"
    )
    _record_promotion(db_path, station_id=station_id, now_ts=now_ts)
    enqueue_station_command(
        db_path,
        station_id=station_id,
        command=StationControlCommand.PROMOTE,
        reason=reason,
    )
    log_recovery_event(
        db_path,
        station_id=station_id,
        event_type="station_promoted",
        old_state="standby",
        new_state="recovering",
        reason=reason,
        action_taken="promote_station",
    )
    return "promoted"
