"""Read-only station health classification from chunks and gaps."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from shared.models import WatchdogSettings


@dataclass(frozen=True)
class StationHealthSnapshot:
    station_id: str
    station_name: str
    enabled: bool
    last_chunk_ts: float | None
    health_state: str
    age_seconds: float | None
    is_stale: bool


def classify_station_health(
    *,
    station_name: str,
    enabled: bool,
    last_chunk_ts: float | None,
    now_ts: float,
    settings: WatchdogSettings,
) -> StationHealthSnapshot:
    """Classify one station as healthy, stale, or disabled."""
    if not enabled:
        return StationHealthSnapshot(
            station_id=station_name,
            station_name=station_name,
            enabled=False,
            last_chunk_ts=last_chunk_ts,
            health_state="disabled",
            age_seconds=None,
            is_stale=False,
        )

    stale_after = settings.station_stale_after_minutes * 60
    if last_chunk_ts is None:
        age_seconds = None
        is_stale = True
    else:
        age_seconds = max(now_ts - last_chunk_ts, 0.0)
        is_stale = age_seconds >= stale_after

    if is_stale:
        health_state = "stale"
    else:
        health_state = "healthy"

    return StationHealthSnapshot(
        station_id=station_name,
        station_name=station_name,
        enabled=True,
        last_chunk_ts=last_chunk_ts,
        health_state=health_state,
        age_seconds=age_seconds,
        is_stale=is_stale,
    )


def load_station_snapshots(
    conn: sqlite3.Connection,
    *,
    now_ts: float,
    settings: WatchdogSettings,
) -> list[StationHealthSnapshot]:
    rows = conn.execute(
        """
        SELECT s.name AS station_name,
               s.enabled AS enabled,
               MAX(c.end_ts) AS last_chunk_ts
        FROM stations s
        LEFT JOIN chunks c ON c.station_id = s.id
        GROUP BY s.id
        ORDER BY s.name
        """
    ).fetchall()
    snapshots: list[StationHealthSnapshot] = []
    for row in rows:
        enabled = bool(row["enabled"])
        last_chunk_ts = float(row["last_chunk_ts"]) if row["last_chunk_ts"] is not None else None
        snapshots.append(
            classify_station_health(
                station_name=row["station_name"],
                enabled=enabled,
                last_chunk_ts=last_chunk_ts,
                now_ts=now_ts,
                settings=settings,
            )
        )
    return snapshots


def count_by_state(snapshots: list[StationHealthSnapshot]) -> dict[str, int]:
    counts: dict[str, int] = {
        "active": 0,
        "healthy": 0,
        "stale": 0,
        "disabled": 0,
    }
    for snap in snapshots:
        if not snap.enabled:
            counts["disabled"] += 1
            continue
        counts["active"] += 1
        if snap.health_state == "stale":
            counts["stale"] += 1
        elif snap.health_state == "healthy":
            counts["healthy"] += 1
    return counts
