"""Replacement pool metadata sync and backup selection."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import StationConfig, WatchdogSettings


def pool_meta_for_station(station: StationConfig) -> dict[str, object]:
    """Derive pool metadata from YAML. Replacement eligibility is explicit opt-in."""
    meta = station.pool or None
    replacement_eligible = meta.replacement_eligible if meta is not None else False
    return {
        "replacement_eligible": replacement_eligible,
        "priority": meta.priority if meta is not None else 100,
        "market": meta.market if meta is not None else None,
        "vertical": meta.vertical if meta is not None else None,
        "needs_stream_resolution": meta.needs_stream_resolution if meta is not None else False,
        "stream_validation_status": meta.stream_validation_status if meta is not None else None,
    }


@retry_on_busy()
def sync_station_pool(
    db_path: str | Path,
    stations: list[StationConfig],
    *,
    settings: WatchdogSettings | None = None,
) -> int:
    """Upsert pool rows from stations.yaml. Returns number of rows written."""
    now_iso = datetime.now(tz=UTC).isoformat()
    conn = get_connection(db_path)
    written = 0
    try:
        with transaction(conn):
            for station in stations:
                meta = pool_meta_for_station(station)
                replacement_update = (
                    "station_pool.replacement_eligible"
                    if settings is not None and settings.fixed_harvest_mode
                    else "excluded.replacement_eligible"
                )
                conn.execute(
                    f"""
                    INSERT INTO station_pool (
                        station_id, replacement_eligible, priority, market, vertical,
                        needs_stream_resolution, stream_validation_status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(station_id) DO UPDATE SET
                        replacement_eligible = {replacement_update},
                        priority = excluded.priority,
                        market = excluded.market,
                        vertical = excluded.vertical,
                        needs_stream_resolution = excluded.needs_stream_resolution,
                        stream_validation_status = excluded.stream_validation_status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        station.name,
                        1 if meta["replacement_eligible"] else 0,
                        int(meta["priority"]),
                        meta["market"],
                        meta["vertical"],
                        1 if meta["needs_stream_resolution"] else 0,
                        meta["stream_validation_status"],
                        now_iso,
                    ),
                )
                written += 1
    finally:
        conn.close()
    return written


def count_active_stations(db_path: str | Path) -> int:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM stations WHERE enabled = 1").fetchone()
        return int(row["n"])
    finally:
        conn.close()


def count_pool_available(db_path: str | Path, *, now_ts: float) -> int:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM station_pool p
            JOIN stations s ON s.name = p.station_id
            LEFT JOIN station_health h ON h.station_id = p.station_id
            WHERE p.replacement_eligible = 1
              AND s.enabled = 0
              AND p.needs_stream_resolution = 0
              AND COALESCE(p.stream_validation_status, '') NOT IN ('fail', 'banned')
              AND COALESCE(h.health_state, 'unknown') NOT IN ('banned', 'permanently_failed')
              AND (
                    h.cool_down_until IS NULL
                    OR h.cool_down_until <= ?
                  )
            """,
            (datetime.fromtimestamp(now_ts, tz=UTC).isoformat(),),
        ).fetchone()
        return int(row["n"])
    finally:
        conn.close()


def _active_urls(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT url FROM stations WHERE enabled = 1"
    ).fetchall()
    return {str(row["url"]) for row in rows}


def _active_market_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT COALESCE(p.market, '') AS market, COUNT(*) AS n
        FROM stations s
        LEFT JOIN station_pool p ON p.station_id = s.name
        WHERE s.enabled = 1
        GROUP BY COALESCE(p.market, '')
        """
    ).fetchall()
    return {str(row["market"]): int(row["n"]) for row in rows}


def select_backup_candidate(
    db_path: str | Path,
    *,
    settings: WatchdogSettings,
    now_ts: float,
) -> dict | None:
    """Pick the best eligible backup station, or None when pool is empty."""
    conn = get_connection(db_path, read_only=True)
    try:
        active_urls = _active_urls(conn)
        market_counts = _active_market_counts(conn)
        cool_cutoff = datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
        rows = conn.execute(
            """
            SELECT s.name AS station_id,
                   s.url AS url,
                   s.format AS format,
                   s.display_name AS display_name,
                   p.priority AS priority,
                   p.market AS market,
                   p.vertical AS vertical
            FROM station_pool p
            JOIN stations s ON s.name = p.station_id
            LEFT JOIN station_health h ON h.station_id = p.station_id
            WHERE p.replacement_eligible = 1
              AND s.enabled = 0
              AND p.needs_stream_resolution = 0
              AND COALESCE(p.stream_validation_status, '') NOT IN ('fail', 'banned')
              AND COALESCE(h.health_state, 'unknown') NOT IN ('banned', 'permanently_failed')
              AND (
                    h.cool_down_until IS NULL
                    OR h.cool_down_until <= ?
                  )
            ORDER BY p.priority ASC, p.vertical ASC, p.market ASC, s.name ASC
            """,
            (cool_cutoff,),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        url = str(row["url"])
        if url in active_urls:
            continue
        market = str(row["market"] or "")
        if market and market_counts.get(market, 0) >= settings.max_active_per_market:
            continue
        return dict(row)
    return None
