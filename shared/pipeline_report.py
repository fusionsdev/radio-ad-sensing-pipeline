"""Build pipeline status / keyword reports for Telegram and operator tools."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from shared.consumer_personal_loan import (
    CLASSIFIER_NAME,
    CLASSIFIER_VERSION,
    TAXONOMY_VERSION,
)


@dataclass(frozen=True)
class PipelineReportSnapshot:
    """Structured pipeline snapshot for periodic Telegram reports."""

    generated_at: float
    since_ts: float
    interval_hours: float
    chunks_by_status: dict[str, int]
    chunks_done_since: int
    pending: int
    enabled_station_count: int
    enabled_stations: tuple[str, ...]
    keyword_hits_total: int
    keyword_hits_since: list[tuple[str, int]]
    top_pending_stations: list[tuple[str, int]]
    down_station_count: int

    def format_telegram(self) -> str:
        """Compact Telegram message (under 4096 chars)."""
        when = datetime.fromtimestamp(self.generated_at, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        since = datetime.fromtimestamp(self.since_ts, tz=UTC).strftime("%H:%M UTC")
        status_bits = ", ".join(
            f"{status} {count}"
            for status, count in sorted(self.chunks_by_status.items())
        )
        lines = [
            f"Pipeline report ({self.interval_hours:g}h) — {when}",
            f"Since {since}",
            f"Queue: {status_bits}",
            f"Done last {self.interval_hours:g}h: {self.chunks_done_since}",
            f"Pending now: {self.pending}",
            f"Stations enabled ({self.enabled_station_count}): "
            + (", ".join(self.enabled_stations[:6]) + ("…" if len(self.enabled_stations) > 6 else "")),
            "",
            f"Classifier: {CLASSIFIER_NAME} {CLASSIFIER_VERSION} (taxonomy {TAXONOMY_VERSION})",
            f"keyword_hits total: {self.keyword_hits_total}",
        ]
        if self.keyword_hits_since:
            hit_bits = ", ".join(f"{kw}×{count}" for kw, count in self.keyword_hits_since[:8])
            lines.append(f"New hits ({self.interval_hours:g}h): {hit_bits}")
        else:
            lines.append(f"New hits ({self.interval_hours:g}h): (none)")
        if self.top_pending_stations:
            pending_bits = ", ".join(f"{name} {count}" for name, count in self.top_pending_stations[:5])
            lines.append(f"Top pending: {pending_bits}")
        if self.down_station_count:
            lines.append(f"Stations down: {self.down_station_count}")
        return "\n".join(lines)


def _int(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def build_pipeline_report_snapshot(
    conn: sqlite3.Connection,
    *,
    now_ts: float | None = None,
    since_ts: float | None = None,
    interval_hours: float = 3.0,
) -> PipelineReportSnapshot:
    """Collect queue + keyword metrics for operator reporting."""
    now = now_ts if now_ts is not None else time.time()
    since = since_ts if since_ts is not None else now - (interval_hours * 3600)

    chunks_by_status = {
        str(row[0]): int(row[1])
        for row in conn.execute(
            "SELECT status, COUNT(*) FROM chunks GROUP BY status"
        ).fetchall()
    }
    pending = _int(conn, "SELECT COUNT(*) FROM chunks WHERE status = 'pending'")
    chunks_done_since = _int(
        conn,
        """
        SELECT COUNT(*) FROM chunks
        WHERE status = 'done' AND start_ts >= ?
        """,
        (since,),
    )
    enabled = conn.execute(
        "SELECT name FROM stations WHERE enabled = 1 ORDER BY name"
    ).fetchall()
    enabled_names = tuple(str(row[0]) for row in enabled)

    keyword_hits_total = _int(conn, "SELECT COUNT(*) FROM keyword_hits")
    keyword_hits_since = [
        (str(row[0]), int(row[1]))
        for row in conn.execute(
            """
            SELECT keyword, COUNT(*) AS n
            FROM keyword_hits
            WHERE hit_ts >= ?
            GROUP BY keyword
            ORDER BY n DESC, keyword
            LIMIT 10
            """,
            (since,),
        ).fetchall()
    ]
    top_pending = [
        (str(row[0]), int(row[1]))
        for row in conn.execute(
            """
            SELECT s.name, COUNT(c.id) AS pending
            FROM stations s
            JOIN chunks c ON c.station_id = s.id AND c.status = 'pending'
            GROUP BY s.id
            ORDER BY pending DESC
            LIMIT 5
            """
        ).fetchall()
    ]
    down_station_count = _int(
        conn,
        """
        SELECT COUNT(DISTINCT g.station_id)
        FROM gaps g
        JOIN stations s ON s.id = g.station_id
        WHERE g.reason = 'stream_down' AND g.end_ts >= ?
        """,
        (since,),
    )

    return PipelineReportSnapshot(
        generated_at=now,
        since_ts=since,
        interval_hours=interval_hours,
        chunks_by_status=chunks_by_status,
        chunks_done_since=chunks_done_since,
        pending=pending,
        enabled_station_count=len(enabled_names),
        enabled_stations=enabled_names,
        keyword_hits_total=keyword_hits_total,
        keyword_hits_since=keyword_hits_since,
        top_pending_stations=top_pending,
        down_station_count=down_station_count,
    )
