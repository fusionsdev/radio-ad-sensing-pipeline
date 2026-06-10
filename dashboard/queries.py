"""Read-only SQL queries for the dashboard."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shared.config import load_settings
from shared.db import get_connection

STALE_CHUNK_AGE_SECONDS = 180.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AD_ARCHIVE_DIR = PROJECT_ROOT / "data" / "ad_archive"
ADS_PAGE_SIZE = 20


@dataclass(frozen=True)
class OverviewStats:
    chunks_today: int
    detections_today: int
    ads_total: int
    queue_depth: int
    station_health: list[dict]


@dataclass(frozen=True)
class AdRow:
    id: int
    company_name: str | None
    category: str | None
    phone_norm: str | None
    first_seen: float
    last_seen: float
    airing_count: int


@dataclass(frozen=True)
class DetectionRow:
    id: int
    chunk_id: int
    company_name: str | None
    offer_summary: str | None
    confidence: float | None
    alerted: bool
    transcript_excerpt: str | None
    station_name: str | None
    chunk_start_ts: float | None


def _start_of_today_ts() -> float:
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp()


def _forty_eight_hours_ago() -> float:
    return time.time() - 48 * 3600


def db_exists(db_path: Path) -> bool:
    return db_path.exists()


def derive_station_status(
    *,
    enabled: bool,
    last_chunk_ts: float | None,
    now: float,
    down_threshold_seconds: float,
    stale_threshold_seconds: float = STALE_CHUNK_AGE_SECONDS,
) -> str:
    """Operator-facing ingest health: disabled | waiting | live | stale | down."""
    if not enabled:
        return "disabled"
    if last_chunk_ts is None:
        return "waiting"
    age_seconds = now - last_chunk_ts
    if age_seconds >= down_threshold_seconds:
        return "down"
    if age_seconds >= stale_threshold_seconds:
        return "stale"
    return "live"


def _enrich_station_row(row: dict, *, now: float, down_threshold_seconds: float) -> dict:
    last_ts = row.get("last_chunk_ts")
    status = derive_station_status(
        enabled=bool(row["enabled"]),
        last_chunk_ts=float(last_ts) if last_ts is not None else None,
        now=now,
        down_threshold_seconds=down_threshold_seconds,
    )
    age_seconds = (now - last_ts) if last_ts is not None else None
    enriched = dict(row)
    enriched["status"] = status
    enriched["age_seconds"] = age_seconds
    return enriched


def fetch_overview(db_path: Path) -> OverviewStats:
    today = _start_of_today_ts()
    now = time.time()
    down_threshold_seconds = load_settings().station_down_alert_minutes * 60
    with _readonly(db_path) as conn:
        chunks_today = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE start_ts >= ?",
            (today,),
        ).fetchone()[0]
        detections_today = conn.execute(
            """
            SELECT COUNT(*) FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            WHERE c.start_ts >= ?
            """,
            (today,),
        ).fetchone()[0]
        ads_total = conn.execute("SELECT COUNT(*) FROM canonical_ads").fetchone()[0]
        queue_depth = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE status = 'pending'"
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.enabled,
                   MAX(c.end_ts) AS last_chunk_ts
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            GROUP BY s.id
            ORDER BY s.name
            """
        ).fetchall()
        station_health = [
            _enrich_station_row(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "enabled": bool(row["enabled"]),
                    "last_chunk_ts": row["last_chunk_ts"],
                },
                now=now,
                down_threshold_seconds=down_threshold_seconds,
            )
            for row in rows
        ]
    return OverviewStats(
        chunks_today=chunks_today,
        detections_today=detections_today,
        ads_total=ads_total,
        queue_depth=queue_depth,
        station_health=station_health,
    )


def fetch_ads_page(db_path: Path, *, page: int = 1) -> tuple[list[AdRow], int]:
    offset = max(page - 1, 0) * ADS_PAGE_SIZE
    with _readonly(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM canonical_ads").fetchone()[0]
        rows = conn.execute(
            """
            SELECT id, company_name, category, phone_norm,
                   first_seen, last_seen, airing_count
            FROM canonical_ads
            ORDER BY last_seen DESC
            LIMIT ? OFFSET ?
            """,
            (ADS_PAGE_SIZE, offset),
        ).fetchall()
    ads = [
        AdRow(
            id=row["id"],
            company_name=row["company_name"],
            category=row["category"],
            phone_norm=row["phone_norm"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            airing_count=row["airing_count"],
        )
        for row in rows
    ]
    return ads, total


def fetch_ad_detail(
    db_path: Path, ad_id: int
) -> tuple[AdRow | None, list[DetectionRow], str | None]:
    with _readonly(db_path) as conn:
        ad_row = conn.execute(
            """
            SELECT id, company_name, category, phone_norm,
                   first_seen, last_seen, airing_count, archived_audio_path
            FROM canonical_ads WHERE id = ?
            """,
            (ad_id,),
        ).fetchone()
        if ad_row is None:
            return None, [], None
        ad = AdRow(
            id=ad_row["id"],
            company_name=ad_row["company_name"],
            category=ad_row["category"],
            phone_norm=ad_row["phone_norm"],
            first_seen=ad_row["first_seen"],
            last_seen=ad_row["last_seen"],
            airing_count=ad_row["airing_count"],
        )
        archived_audio_path = ad_row["archived_audio_path"]
        det_rows = conn.execute(
            """
            SELECT d.id, d.chunk_id, d.company_name, d.offer_summary,
                   d.confidence, d.alerted, d.key_claims,
                   t.text AS transcript_text,
                   s.name AS station_name, c.start_ts AS chunk_start_ts
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
            WHERE d.canonical_ad_id = ?
            ORDER BY c.start_ts DESC
            """,
            (ad_id,),
        ).fetchall()
    detections = []
    for row in det_rows:
        excerpt = row["transcript_text"]
        if excerpt and len(excerpt) > 200:
            excerpt = excerpt[:200] + "…"
        detections.append(
            DetectionRow(
                id=row["id"],
                chunk_id=row["chunk_id"],
                company_name=row["company_name"],
                offer_summary=row["offer_summary"],
                confidence=row["confidence"],
                alerted=bool(row["alerted"]),
                transcript_excerpt=excerpt,
                station_name=row["station_name"],
                chunk_start_ts=row["chunk_start_ts"],
            )
        )
    return ad, detections, archived_audio_path


def fetch_stations(db_path: Path) -> list[dict]:
    now = time.time()
    since_24h = now - 24 * 3600
    down_threshold_seconds = load_settings().station_down_alert_minutes * 60
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.enabled, s.url,
                   MAX(c.end_ts) AS last_chunk_ts,
                   SUM(CASE WHEN c.start_ts >= ? THEN 1 ELSE 0 END) AS chunks_24h,
                   (
                     SELECT COUNT(*) FROM gaps g
                     WHERE g.station_id = s.id AND g.start_ts >= ?
                   ) AS gaps_24h
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            GROUP BY s.id
            ORDER BY s.name
            """,
            (since_24h, since_24h),
        ).fetchall()
    return [
        _enrich_station_row(dict(row), now=now, down_threshold_seconds=down_threshold_seconds)
        for row in rows
    ]


def fetch_gaps(db_path: Path) -> list[dict]:
    since = _forty_eight_hours_ago()
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.station_id, s.name AS station_name,
                   g.start_ts, g.end_ts, g.reason
            FROM gaps g
            JOIN stations s ON s.id = g.station_id
            WHERE g.start_ts >= ?
            ORDER BY g.start_ts DESC
            """,
            (since,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_health(db_path: Path) -> dict:
    if not db_exists(db_path):
        return {"db_reachable": False, "pending_count": 0}
    try:
        with _readonly(db_path) as conn:
            pending = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE status = 'pending'"
            ).fetchone()[0]
        return {"db_reachable": True, "pending_count": pending}
    except Exception:
        return {"db_reachable": False, "pending_count": 0}


def resolve_audio_path(db_path: Path, resource_id: int) -> Path | None:
    """Resolve audio file strictly inside data/ad_archive/."""
    archive_root = AD_ARCHIVE_DIR.resolve()
    with _readonly(db_path) as conn:
        row = conn.execute(
            """
            SELECT ca.archived_audio_path
            FROM detections d
            JOIN canonical_ads ca ON ca.id = d.canonical_ad_id
            WHERE d.id = ?
            """,
            (resource_id,),
        ).fetchone()
        if row is None or not row["archived_audio_path"]:
            row = conn.execute(
                "SELECT archived_audio_path FROM canonical_ads WHERE id = ?",
                (resource_id,),
            ).fetchone()
        if row is None or not row["archived_audio_path"]:
            return None
        stored = row["archived_audio_path"]
        candidate = Path(stored)
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        else:
            candidate = candidate.resolve()
        try:
            candidate.relative_to(archive_root)
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        return candidate


@contextmanager
def _readonly(db_path: Path):
    connection = get_connection(db_path, read_only=True)
    try:
        yield connection
    finally:
        connection.close()
