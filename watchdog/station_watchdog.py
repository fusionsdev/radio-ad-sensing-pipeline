"""Watchdog loop: health detection, stale alerting, and auto-restart."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from shared.queue_health import compute_queue_drop_ratio
from shared.config import load_settings
from shared.db import get_connection
from shared.metrics import (
    increment_station_promotions,
    increment_station_restarts,
    record_watchdog_loop,
    set_queue_dropped_done_ratio,
    set_station_health_counts,
    set_station_last_chunk_age,
    set_station_pool_available,
)
from shared.models import WatchdogSettings
from watchdog.health import count_by_state, load_station_snapshots
from watchdog.notify import QueueSnapshot, send_stale_station_alert
from watchdog.pool import count_pool_available
from watchdog.promotion import maybe_promote_backup
from watchdog.recovery import auto_restart_stale_station
from watchdog.repository import clear_stale_alert_marker, record_stale_detection, sync_station_health

logger = logging.getLogger(__name__)


def queue_snapshot(db_path: Path, settings: WatchdogSettings) -> QueueSnapshot:
    conn = get_connection(db_path, read_only=True)
    try:
        done = int(conn.execute("SELECT COUNT(*) FROM chunks WHERE status = 'done'").fetchone()[0])
        dropped = int(
            conn.execute("SELECT COUNT(*) FROM chunks WHERE status = 'dropped'").fetchone()[0]
        )
        pending = int(
            conn.execute("SELECT COUNT(*) FROM chunks WHERE status = 'pending'").fetchone()[0]
        )
    finally:
        conn.close()
    ratio = compute_queue_drop_ratio(dropped=dropped, done=done)
    if ratio >= settings.queue_drop_ratio_critical:
        level = "critical"
    elif ratio >= settings.queue_drop_ratio_warning:
        level = "warning"
    else:
        level = "ok"
    return QueueSnapshot(
        done=done,
        dropped=dropped,
        pending=pending,
        drop_ratio=ratio,
        level=level,
    )


def run_health_check(db_path: Path, *, settings: WatchdogSettings | None = None) -> dict:
    """Run one watchdog pass. Returns summary dict for tests and dashboard."""
    settings = settings or load_settings().watchdog
    started = time.perf_counter()
    now_ts = time.time()

    conn = get_connection(db_path, read_only=True)
    try:
        snapshots = load_station_snapshots(conn, now_ts=now_ts, settings=settings)
    finally:
        conn.close()

    sync_station_health(db_path, snapshots)
    counts = count_by_state(snapshots)
    queue = queue_snapshot(db_path, settings)

    stale_alerts_sent = 0
    restarts_queued = 0
    stations_disabled = 0
    for snap in snapshots:
        set_station_last_chunk_age(snap.station_name, snap.age_seconds)
        if snap.health_state == "healthy" and snap.enabled:
            clear_stale_alert_marker(db_path, snap.station_id)
            continue
        if not snap.is_stale:
            continue

        new_episode = record_stale_detection(db_path, snap, now_ts=now_ts)
        recovery_action = None
        if new_episode:
            recovery_action = auto_restart_stale_station(
                db_path,
                snap,
                settings=settings,
                now_ts=now_ts,
            )
            if recovery_action == "restart_queued":
                restarts_queued += 1
                increment_station_restarts()
            elif recovery_action == "disabled":
                stations_disabled += 1

            if send_stale_station_alert(
                snap,
                active_count=counts["active"],
                target_count=settings.target_active_stations,
                queue=queue,
                stale_minutes=settings.station_stale_after_minutes,
                recovery_action=recovery_action,
                settings=settings,
            ):
                stale_alerts_sent += 1
            logger.warning(
                "station stale",
                extra={
                    "station": snap.station_name,
                    "age_seconds": snap.age_seconds,
                    "queue_ratio": queue.drop_ratio,
                    "recovery_action": recovery_action,
                },
            )

    failed_count = _count_failed_stations(db_path)
    pool_available = count_pool_available(db_path, now_ts=now_ts)
    promotion_action = maybe_promote_backup(
        db_path,
        settings=settings,
        queue=queue,
        now_ts=now_ts,
    )
    if promotion_action == "promoted":
        increment_station_promotions()

    elapsed = time.perf_counter() - started
    set_station_health_counts(
        active=counts["active"],
        healthy=counts["healthy"],
        stale=counts["stale"],
        failed=failed_count,
    )
    set_station_pool_available(pool_available)
    set_queue_dropped_done_ratio(queue.drop_ratio)
    record_watchdog_loop(elapsed)

    return {
        "counts": counts,
        "target_active_stations": settings.target_active_stations,
        "queue": queue,
        "stale_alerts_sent": stale_alerts_sent,
        "restarts_queued": restarts_queued,
        "stations_disabled": stations_disabled,
        "promotion_action": promotion_action,
        "pool_available": pool_available,
        "stations": snapshots,
        "loop_seconds": elapsed,
    }


def _count_failed_stations(db_path: Path) -> int:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM station_health WHERE health_state = 'failed'"
        ).fetchone()
        return int(row["n"])
    finally:
        conn.close()
