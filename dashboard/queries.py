"""Read-only SQL queries for the dashboard."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dashboard.stats import (
    compute_queue_drop_ratio,
    compute_yield_pct,
    derive_review_tier,
    derive_slot_recommendation,
    queue_drop_warning,
)
from shared.config import load_settings, load_stations, load_vertical_keywords
from shared.db import get_connection
from shared.verticals import (
    VerticalHitSummary,
    fetch_vertical_summaries_from_db,
    keyword_to_vertical_map,
)

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
    queue_done: int
    queue_dropped: int
    queue_drop_ratio: float
    queue_drop_warning: bool
    keyword_hits_total: int
    station_health: list[dict]
    vertical_summaries: list[VerticalHitSummary]


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


@dataclass(frozen=True)
class KeywordHitRow:
    id: int
    keyword: str
    vertical: str | None
    vertical_label: str | None
    station_label: str
    hit_ts: float
    chunk_id: int
    context_excerpt: str | None
    detection_id: int | None


@dataclass(frozen=True)
class AdvertiserOpportunityRow:
    id: int
    vertical: str
    vertical_label: str
    station_label: str
    company_name: str | None
    domain: str | None
    phone_number: str | None
    vanity_phone: str | None
    offer_summary: str | None
    cta: str | None
    hit_ts: float
    chunk_id: int
    audio_clip_path: str | None
    source_keywords: tuple[str, ...]
    confidence: float | None
    approved: bool


@dataclass(frozen=True)
class ReviewRow:
    chunk_id: int
    chunk_start_ts: float
    station_label: str
    tier: str
    keywords: tuple[str, ...]
    keyword_excerpt: str | None
    transcript_excerpt: str | None
    detection_id: int | None
    canonical_ad_id: int | None
    company_name: str | None
    ad_category: str | None
    phone_number: str | None
    website: str | None
    offer_summary: str | None
    confidence: float | None
    alerted: bool


def _start_of_today_ts() -> float:
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp()


def _forty_eight_hours_ago() -> float:
    return time.time() - 48 * 3600


def _seven_days_ago() -> float:
    return time.time() - 7 * 24 * 3600


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


def _parse_iso_ts(value: object) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _load_ingestor_health(conn) -> dict[str, dict]:
    health: dict[str, dict] = {}
    try:
        rows = conn.execute(
            """
            SELECT station_id, health_state, last_success_at, last_failure_at,
                   consecutive_failures, cool_down_until, last_error
            FROM station_health
            """
        ).fetchall()
    except Exception:
        rows = []
    for row in rows:
        health[str(row["station_id"])] = {
            "status": row["health_state"],
            "last_success_at": _parse_iso_ts(row["last_success_at"]),
            "last_failure_at": _parse_iso_ts(row["last_failure_at"]),
            "consecutive_failures": int(row["consecutive_failures"] or 0),
            "backoff_until": _parse_iso_ts(row["cool_down_until"]),
            "ffmpeg_error_sample": row["last_error"] or "",
        }

    try:
        rows = conn.execute(
            """
            SELECT key, value
            FROM status
            WHERE key LIKE 'ingestor:station_health:%'
            """
        ).fetchall()
    except Exception:
        rows = []
    prefix = "ingestor:station_health:"
    for row in rows:
        key = str(row["key"])
        if not key.startswith(prefix):
            continue
        try:
            payload = json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            continue
        station_name = key.removeprefix(prefix)
        item = health.setdefault(station_name, {})
        item.update(
            {
                "status": payload.get("status", item.get("status")),
                "last_success_at": payload.get("last_success_at", item.get("last_success_at")),
                "last_failure_at": payload.get("last_failure_at", item.get("last_failure_at")),
                "consecutive_empty_chunks": int(
                    payload.get("consecutive_empty_chunks") or 0
                ),
                "consecutive_stream_down": int(
                    payload.get("consecutive_stream_down") or 0
                ),
                "attempts_since_success": int(payload.get("attempts_since_success") or 0),
                "backoff_until": payload.get("backoff_until", item.get("backoff_until")),
                "ffmpeg_error_sample": payload.get(
                    "last_ffmpeg_error_sample",
                    item.get("ffmpeg_error_sample", ""),
                ),
                "url_hash": payload.get("url_hash"),
            }
        )
    return health


def _load_gap_counts_30m(conn, *, now: float) -> dict[str, dict[str, int]]:
    since = now - 30 * 60
    rows = conn.execute(
        """
        SELECT s.name AS station_name, g.reason, COUNT(*) AS n
        FROM gaps g
        JOIN stations s ON s.id = g.station_id
        WHERE g.start_ts >= ?
          AND g.reason IN ('empty_chunk', 'stream_down')
        GROUP BY s.name, g.reason
        """,
        (since,),
    ).fetchall()
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        station_counts = counts.setdefault(str(row["station_name"]), {})
        station_counts[str(row["reason"])] = int(row["n"] or 0)
    return counts


def _derive_ingestor_status(
    *,
    enabled: bool,
    legacy_status: str,
    health: dict,
    now: float,
) -> str:
    if not enabled:
        return "paused"
    health_status = str(health.get("status") or "")
    backoff_until = health.get("backoff_until")
    if isinstance(backoff_until, (int, float)) and backoff_until > now:
        return "backoff"
    if health_status == "backoff" and backoff_until is None:
        return "backoff"
    if health_status in {"degraded", "failed", "stale"}:
        return "degraded"
    if legacy_status in {"waiting", "stale", "down"}:
        return "degraded"
    return "healthy"


def _enrich_station_row(
    row: dict,
    *,
    now: float,
    down_threshold_seconds: float,
    ingestor_health: dict[str, dict] | None = None,
    gap_counts_30m: dict[str, dict[str, int]] | None = None,
) -> dict:
    last_ts = row.get("last_chunk_ts")
    legacy_status = derive_station_status(
        enabled=bool(row["enabled"]),
        last_chunk_ts=float(last_ts) if last_ts is not None else None,
        now=now,
        down_threshold_seconds=down_threshold_seconds,
    )
    age_seconds = (now - last_ts) if last_ts is not None else None
    station_name = str(row.get("name") or row.get("station_name") or "")
    health = (ingestor_health or {}).get(station_name, {})
    gaps = (gap_counts_30m or {}).get(station_name, {})
    status = _derive_ingestor_status(
        enabled=bool(row["enabled"]),
        legacy_status=legacy_status,
        health=health,
        now=now,
    )
    enriched = dict(row)
    enriched["legacy_status"] = legacy_status
    enriched["status"] = status
    enriched["age_seconds"] = age_seconds
    enriched["last_valid_chunk_age_seconds"] = age_seconds
    enriched["empty_chunk_count_30m"] = int(gaps.get("empty_chunk") or 0)
    enriched["stream_down_count_30m"] = int(gaps.get("stream_down") or 0)
    enriched["last_success_at"] = health.get("last_success_at")
    enriched["last_failure_at"] = health.get("last_failure_at")
    enriched["consecutive_empty_chunks"] = int(health.get("consecutive_empty_chunks") or 0)
    enriched["consecutive_stream_down"] = int(health.get("consecutive_stream_down") or 0)
    enriched["backoff_until"] = health.get("backoff_until")
    enriched["ffmpeg_error_sample"] = health.get("ffmpeg_error_sample") or ""
    enriched["url_hash"] = health.get("url_hash")
    enriched["station_label"] = station_label(enriched)
    return enriched


def station_label(row: dict[str, object]) -> str:
    """Human-readable station name for dashboard (display_name fallback to slug)."""
    display = row.get("display_name")
    name = str(row.get("name") or row.get("station_name") or "")
    if display and str(display).strip():
        return str(display).strip()
    labels = _yaml_station_label_map()
    if name in labels:
        return labels[name]
    return name


def _yaml_station_label_map() -> dict[str, str]:
    return {
        station.name: station.display_name or station.name
        for station in load_stations()
        if station.display_name
    }


def _apply_yaml_labels(rows: list[dict]) -> list[dict]:
    """Fill missing display_name from stations.yaml for dashboard readability."""
    labels = _yaml_station_label_map()
    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        if not item.get("display_name") and item.get("name") in labels:
            item["display_name"] = labels[str(item["name"])]
        item["station_label"] = station_label(item)
        enriched.append(item)
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
        queue_done = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE status = 'done'"
        ).fetchone()[0]
        queue_dropped = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE status = 'dropped'"
        ).fetchone()[0]
        keyword_hits_total = conn.execute("SELECT COUNT(*) FROM keyword_hits").fetchone()[0]
        vertical_config = load_vertical_keywords()
        drop_threshold = vertical_config.settings.queue_drop_ratio_warn_threshold
        drop_ratio = compute_queue_drop_ratio(dropped=int(queue_dropped), done=int(queue_done))
        drop_warn = queue_drop_warning(
            dropped=int(queue_dropped),
            done=int(queue_done),
            threshold=drop_threshold,
        )
        vertical_summaries = fetch_vertical_summaries_from_db(conn, config=vertical_config)
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.display_name, s.enabled,
                   MAX(c.end_ts) AS last_chunk_ts
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            GROUP BY s.id
            ORDER BY s.name
            """
        ).fetchall()
        ingestor_health = _load_ingestor_health(conn)
        gap_counts_30m = _load_gap_counts_30m(conn, now=now)
        station_health = [
            _enrich_station_row(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "display_name": row["display_name"],
                    "enabled": bool(row["enabled"]),
                    "last_chunk_ts": row["last_chunk_ts"],
                },
                now=now,
                down_threshold_seconds=down_threshold_seconds,
                ingestor_health=ingestor_health,
                gap_counts_30m=gap_counts_30m,
            )
            for row in rows
        ]
    return OverviewStats(
        chunks_today=chunks_today,
        detections_today=detections_today,
        ads_total=ads_total,
        queue_depth=queue_depth,
        queue_done=int(queue_done),
        queue_dropped=int(queue_dropped),
        queue_drop_ratio=drop_ratio,
        queue_drop_warning=drop_warn,
        keyword_hits_total=int(keyword_hits_total),
        station_health=station_health,
        vertical_summaries=vertical_summaries,
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
                   s.name AS station_name, c.start_ts AS chunk_start_ts,
                   s.display_name AS station_display_name
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
                station_name=station_label(
                    {
                        "name": row["station_name"],
                        "display_name": row["station_display_name"],
                    }
                ),
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
            SELECT s.id, s.name, s.display_name, s.enabled, s.url,
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
        ingestor_health = _load_ingestor_health(conn)
        gap_counts_30m = _load_gap_counts_30m(conn, now=now)
    return [
        _enrich_station_row(
            dict(row),
            now=now,
            down_threshold_seconds=down_threshold_seconds,
            ingestor_health=ingestor_health,
            gap_counts_30m=gap_counts_30m,
        )
        for row in rows
    ]


def fetch_gaps(db_path: Path) -> list[dict]:
    since = _forty_eight_hours_ago()
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.station_id, s.name AS station_name,
                   s.display_name AS station_display_name,
                   g.start_ts, g.end_ts, g.reason
            FROM gaps g
            JOIN stations s ON s.id = g.station_id
            WHERE g.start_ts >= ?
            ORDER BY g.start_ts DESC
            """,
            (since,),
        ).fetchall()
    return [
        {
            **dict(row),
            "station_label": station_label(
                {"name": row["station_name"], "display_name": row["station_display_name"]}
            ),
        }
        for row in rows
    ]


def fetch_station_scorecard(db_path: Path, *, window_days: int = 7) -> list[dict]:
    """Per-station ops health + keyword yield for slot decisions."""
    now = time.time()
    since = now - window_days * 24 * 3600
    down_threshold_seconds = load_settings().station_down_alert_minutes * 60
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.display_name, s.enabled,
                   MAX(c.end_ts) AS last_chunk_ts,
                   SUM(CASE WHEN c.start_ts >= ? THEN 1 ELSE 0 END) AS chunks_7d,
                   (
                     SELECT COUNT(*) FROM gaps g
                     WHERE g.station_id = s.id AND g.start_ts >= ?
                   ) AS gaps_7d,
                   (
                     SELECT COUNT(*) FROM keyword_hits kh
                     WHERE kh.station_id = s.id AND kh.hit_ts >= ?
                   ) AS keyword_hits_7d,
                   (
                     SELECT COUNT(DISTINCT kh.keyword) FROM keyword_hits kh
                     WHERE kh.station_id = s.id AND kh.hit_ts >= ?
                   ) AS unique_keywords_7d,
                   (
                     SELECT COUNT(*) FROM detections d
                     JOIN chunks dc ON dc.id = d.chunk_id
                     WHERE dc.station_id = s.id
                       AND dc.start_ts >= ?
                       AND d.is_ad = 1
                   ) AS loan_detections_7d
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            GROUP BY s.id
            ORDER BY keyword_hits_7d DESC, s.name
            """,
            (since, since, since, since, since),
        ).fetchall()

    scorecard: list[dict] = []
    for row in rows:
        enriched = _enrich_station_row(dict(row), now=now, down_threshold_seconds=down_threshold_seconds)
        chunks_7d = int(enriched.get("chunks_7d") or 0)
        keyword_hits_7d = int(enriched.get("keyword_hits_7d") or 0)
        yield_pct = compute_yield_pct(keyword_hits=keyword_hits_7d, chunks=chunks_7d)
        enriched["yield_pct"] = yield_pct
        enriched["recommendation"] = derive_slot_recommendation(
            enabled=bool(enriched["enabled"]),
            status=str(enriched["status"]),
            chunks_7d=chunks_7d,
            keyword_hits_7d=keyword_hits_7d,
            yield_pct=yield_pct,
        )
        scorecard.append(enriched)
    scorecard.sort(
        key=lambda row: (
            {"swap": 0, "fix": 1, "review": 2, "keep": 3, "bench": 4}.get(
                str(row["recommendation"]), 5
            ),
            -float(row.get("keyword_hits_7d") or 0),
            str(row["name"]),
        )
    )
    return scorecard


def _truncate_excerpt(text: str | None, *, limit: int = 320) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def fetch_review_inbox(
    db_path: Path,
    *,
    window_days: int = 7,
    tier: str | None = None,
    limit: int = 200,
) -> list[ReviewRow]:
    """Chunks with keyword hits and/or LLM ad detections for operator review."""
    since = time.time() - window_days * 24 * 3600
    tier_filter = tier.upper() if tier else None
    if tier_filter is not None and tier_filter not in {"A", "B", "C"}:
        tier_filter = None

    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.id AS chunk_id,
                   c.start_ts AS chunk_start_ts,
                   s.name AS station_name,
                   s.display_name AS station_display_name,
                   t.text AS transcript_text,
                   (
                     SELECT GROUP_CONCAT(DISTINCT kh.keyword)
                     FROM keyword_hits kh
                     WHERE kh.chunk_id = c.id
                   ) AS keywords_csv,
                   (
                     SELECT GROUP_CONCAT(DISTINCT kh.context_excerpt)
                     FROM keyword_hits kh
                     WHERE kh.chunk_id = c.id
                       AND kh.context_excerpt IS NOT NULL
                       AND TRIM(kh.context_excerpt) != ''
                   ) AS keyword_excerpt,
                   d.id AS detection_id,
                   d.canonical_ad_id,
                   d.company_name,
                   d.ad_category,
                   d.phone_number,
                   d.website,
                   d.offer_summary,
                   d.confidence,
                   d.alerted
            FROM chunks c
            JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = c.id
            LEFT JOIN detections d ON d.chunk_id = c.id AND d.is_ad = 1
            WHERE c.start_ts >= ?
              AND (
                EXISTS (SELECT 1 FROM keyword_hits kh WHERE kh.chunk_id = c.id)
                OR d.id IS NOT NULL
              )
            ORDER BY c.start_ts DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()

    labels = _yaml_station_label_map()
    inbox: list[ReviewRow] = []
    for row in rows:
        keywords_csv = row["keywords_csv"]
        keywords = tuple(
            sorted({part.strip() for part in (keywords_csv or "").split(",") if part.strip()})
        )
        has_keywords = bool(keywords)
        has_ad = row["detection_id"] is not None
        row_tier = derive_review_tier(has_keywords=has_keywords, has_ad_detection=has_ad)
        if tier_filter is not None and row_tier != tier_filter:
            continue

        station_name = str(row["station_name"])
        display_name = row["station_display_name"]
        station_label_text = (
            str(display_name).strip()
            if display_name and str(display_name).strip()
            else labels.get(station_name, station_name)
        )
        keyword_excerpt = _truncate_excerpt(row["keyword_excerpt"], limit=200)
        transcript_excerpt = _truncate_excerpt(row["transcript_text"])
        if keyword_excerpt and transcript_excerpt and keyword_excerpt in transcript_excerpt:
            keyword_excerpt = None

        inbox.append(
            ReviewRow(
                chunk_id=int(row["chunk_id"]),
                chunk_start_ts=float(row["chunk_start_ts"]),
                station_label=station_label_text,
                tier=row_tier,
                keywords=keywords,
                keyword_excerpt=keyword_excerpt,
                transcript_excerpt=transcript_excerpt,
                detection_id=int(row["detection_id"]) if row["detection_id"] is not None else None,
                canonical_ad_id=int(row["canonical_ad_id"])
                if row["canonical_ad_id"] is not None
                else None,
                company_name=row["company_name"],
                ad_category=row["ad_category"],
                phone_number=row["phone_number"],
                website=row["website"],
                offer_summary=row["offer_summary"],
                confidence=float(row["confidence"]) if row["confidence"] is not None else None,
                alerted=bool(row["alerted"]) if row["detection_id"] is not None else False,
            )
        )
    return inbox


def fetch_keyword_matrix(
    db_path: Path, *, window_days: int = 7
) -> tuple[list[str], list[str], dict[str, dict[str, int]]]:
    """Return station names, keywords, and station -> keyword -> hit count."""
    since = time.time() - window_days * 24 * 3600
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.name AS station_name, s.display_name AS station_display_name,
                   kh.keyword, COUNT(*) AS hits
            FROM keyword_hits kh
            JOIN stations s ON s.id = kh.station_id
            WHERE kh.hit_ts >= ?
            GROUP BY s.name, s.display_name, kh.keyword
            ORDER BY kh.keyword, s.name
            """,
            (since,),
        ).fetchall()

    matrix: dict[str, dict[str, int]] = {}
    stations: set[str] = set()
    keywords: set[str] = set()
    labels = _yaml_station_label_map()
    for row in rows:
        station_name = str(row["station_name"])
        display_name = row["station_display_name"]
        station_label_text = (
            str(display_name).strip()
            if display_name and str(display_name).strip()
            else labels.get(station_name, station_name)
        )
        keyword = str(row["keyword"])
        stations.add(station_label_text)
        keywords.add(keyword)
        matrix.setdefault(station_label_text, {})[keyword] = int(row["hits"])

    return sorted(stations), sorted(keywords), matrix


def fetch_keyword_hits(
    db_path: Path,
    *,
    window_days: int = 7,
    vertical: str | None = None,
    limit: int = 500,
) -> list[KeywordHitRow]:
    """All raw keyword hits with vertical mapping for dashboard."""
    since = time.time() - window_days * 24 * 3600
    vertical_config = load_vertical_keywords()
    kw_map = keyword_to_vertical_map(vertical_config)
    labels = {vid: v.label for vid, v in vertical_config.verticals.items()}

    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT kh.id, kh.keyword, kh.hit_ts, kh.chunk_id,
                   kh.context_excerpt, kh.detection_id,
                   s.name AS station_name, s.display_name AS station_display_name
            FROM keyword_hits kh
            JOIN stations s ON s.id = kh.station_id
            WHERE kh.hit_ts >= ?
            ORDER BY kh.hit_ts DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()

    hits: list[KeywordHitRow] = []
    yaml_labels = _yaml_station_label_map()
    for row in rows:
        keyword = str(row["keyword"])
        vertical_id = kw_map.get(keyword.lower())
        if vertical is not None and vertical_id != vertical:
            continue
        station_name = str(row["station_name"])
        display_name = row["station_display_name"]
        station_label_text = (
            str(display_name).strip()
            if display_name and str(display_name).strip()
            else yaml_labels.get(station_name, station_name)
        )
        hits.append(
            KeywordHitRow(
                id=int(row["id"]),
                keyword=keyword,
                vertical=vertical_id,
                vertical_label=labels.get(vertical_id) if vertical_id else None,
                station_label=station_label_text,
                hit_ts=float(row["hit_ts"]),
                chunk_id=int(row["chunk_id"]),
                context_excerpt=row["context_excerpt"],
                detection_id=int(row["detection_id"])
                if row["detection_id"] is not None
                else None,
            )
        )
    return hits


def fetch_vertical_summaries(
    db_path: Path, *, window_days: int = 7
) -> list[VerticalHitSummary]:
    since = time.time() - window_days * 24 * 3600
    with _readonly(db_path) as conn:
        return fetch_vertical_summaries_from_db(conn, since=since)


def fetch_vertical_detail(
    db_path: Path,
    vertical_id: str,
    *,
    window_days: int = 7,
) -> tuple[VerticalHitSummary | None, list[KeywordHitRow], list[AdvertiserOpportunityRow]]:
    summaries = fetch_vertical_summaries(db_path, window_days=window_days)
    summary = next((s for s in summaries if s.vertical == vertical_id), None)
    hits = fetch_keyword_hits(
        db_path, window_days=window_days, vertical=vertical_id, limit=200
    )
    opportunities = fetch_advertiser_opportunities(
        db_path, vertical=vertical_id, window_days=window_days
    )
    return summary, hits, opportunities


def fetch_advertiser_opportunities(
    db_path: Path,
    *,
    vertical: str | None = None,
    window_days: int = 30,
    limit: int = 200,
) -> list[AdvertiserOpportunityRow]:
    since = time.time() - window_days * 24 * 3600
    vertical_config = load_vertical_keywords()
    labels = {vid: v.label for vid, v in vertical_config.verticals.items()}
    params: list = [since, limit]
    vertical_clause = ""
    if vertical is not None:
        vertical_clause = "AND ao.vertical = ?"
        params = [since, vertical, limit]

    with _readonly(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT ao.id, ao.vertical, ao.company_name, ao.domain,
                   ao.phone_number, ao.vanity_phone, ao.offer_summary, ao.cta,
                   ao.hit_ts, ao.chunk_id, ao.audio_clip_path,
                   ao.source_keywords, ao.confidence, ao.approved,
                   s.name AS station_name, s.display_name AS station_display_name
            FROM advertiser_opportunities ao
            JOIN stations s ON s.id = ao.station_id
            WHERE ao.hit_ts >= ? {vertical_clause}
            ORDER BY ao.hit_ts DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    yaml_labels = _yaml_station_label_map()
    results: list[AdvertiserOpportunityRow] = []
    for row in rows:
        station_name = str(row["station_name"])
        display_name = row["station_display_name"]
        station_label_text = (
            str(display_name).strip()
            if display_name and str(display_name).strip()
            else yaml_labels.get(station_name, station_name)
        )
        raw_kw = row["source_keywords"] or "[]"
        try:
            keywords = tuple(json.loads(raw_kw))
        except json.JSONDecodeError:
            keywords = ()
        results.append(
            AdvertiserOpportunityRow(
                id=int(row["id"]),
                vertical=str(row["vertical"]),
                vertical_label=labels.get(str(row["vertical"]), str(row["vertical"])),
                station_label=station_label_text,
                company_name=row["company_name"],
                domain=row["domain"],
                phone_number=row["phone_number"],
                vanity_phone=row["vanity_phone"],
                offer_summary=row["offer_summary"],
                cta=row["cta"],
                hit_ts=float(row["hit_ts"]),
                chunk_id=int(row["chunk_id"]),
                audio_clip_path=row["audio_clip_path"],
                source_keywords=keywords,
                confidence=float(row["confidence"]) if row["confidence"] is not None else None,
                approved=bool(row["approved"]),
            )
        )
    return results


def fetch_queue_health(db_path: Path) -> dict:
    """Queue done/dropped counts and drop ratio for dashboard warnings."""
    settings = load_settings()
    vertical_config = load_vertical_keywords()
    threshold = vertical_config.settings.queue_drop_ratio_warn_threshold
    with _readonly(db_path) as conn:
        done = int(
            conn.execute("SELECT COUNT(*) FROM chunks WHERE status = 'done'").fetchone()[0]
        )
        dropped = int(
            conn.execute("SELECT COUNT(*) FROM chunks WHERE status = 'dropped'").fetchone()[0]
        )
        pending = int(
            conn.execute("SELECT COUNT(*) FROM chunks WHERE status = 'pending'").fetchone()[0]
        )
    ratio = compute_queue_drop_ratio(dropped=dropped, done=done)
    return {
        "done": done,
        "dropped": dropped,
        "pending": pending,
        "drop_ratio": ratio,
        "drop_warning": queue_drop_warning(dropped=dropped, done=done, threshold=threshold),
        "threshold": threshold,
    }


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


def cfpb_tables_available(db_path: Path) -> bool:
    if not db_exists(db_path):
        return False
    with _readonly(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cfpb_brand_candidates'"
        ).fetchone()
        return row is not None


def fetch_cfpb_overview(db_path: Path) -> dict[str, int]:
    with _readonly(db_path) as conn:
        return {
            "raw": int(conn.execute("SELECT COUNT(*) FROM cfpb_complaints_raw").fetchone()[0]),
            "entities": int(conn.execute("SELECT COUNT(*) FROM cfpb_company_entities").fetchone()[0]),
            "candidates": int(conn.execute("SELECT COUNT(*) FROM cfpb_brand_candidates").fetchone()[0]),
            "candidates_70": int(
                conn.execute("SELECT COUNT(*) FROM cfpb_brand_candidates WHERE score >= 70").fetchone()[0]
            ),
            "candidates_85": int(
                conn.execute("SELECT COUNT(*) FROM cfpb_brand_candidates WHERE score >= 85").fetchone()[0]
            ),
            "runs": int(conn.execute("SELECT COUNT(*) FROM cfpb_collection_runs").fetchone()[0]),
        }


def fetch_cfpb_candidates(
    db_path: Path, *, min_score: float = 0.0, limit: int = 200
) -> list[dict[str, object]]:
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.candidate_name, c.normalized_candidate, c.candidate_type,
                   c.score, c.verification_status, c.source_product, c.source_state,
                   e.company_raw, e.complaint_count, e.trademark_candidate_score
            FROM cfpb_brand_candidates c
            LEFT JOIN cfpb_company_entities e ON e.id = c.cfpb_company_entity_id
            WHERE c.score >= ?
            ORDER BY c.score DESC, c.id DESC
            LIMIT ?
            """,
            (min_score, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_cfpb_candidate_detail(db_path: Path, candidate_id: int) -> dict[str, object] | None:
    with _readonly(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.*, e.company_raw, e.company_normalized, e.complaint_count,
                   e.narrative_count, e.trademark_candidate_score, e.review_status AS entity_review_status
            FROM cfpb_brand_candidates c
            LEFT JOIN cfpb_company_entities e ON e.id = c.cfpb_company_entity_id
            WHERE c.id = ?
            """,
            (candidate_id,),
        ).fetchone()
    return dict(row) if row else None


def fetch_cfpb_runs(db_path: Path, *, limit: int = 20) -> list[dict[str, object]]:
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, finished_at, source_mode, records_seen, records_inserted,
                   entities_created, candidates_created, status, error_message
            FROM cfpb_collection_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_cfpb_entities(db_path: Path, *, limit: int = 200) -> list[dict[str, object]]:
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, company_raw, company_normalized, complaint_count, narrative_count,
                   trademark_candidate_score, review_status, first_seen_at, last_seen_at
            FROM cfpb_company_entities
            ORDER BY trademark_candidate_score DESC, complaint_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def watchdog_tables_available(db_path: Path) -> bool:
    if not db_path.is_file():
        return False
    conn = get_connection(db_path, read_only=True)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    finally:
        conn.close()
    return "station_health" in tables and "station_recovery_events" in tables


def control_commands_available(db_path: Path) -> bool:
    if not db_path.is_file():
        return False
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='station_control_commands'"
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def fetch_watchdog_overview(db_path: Path) -> dict:
    """Watchdog ops summary for /ops/watchdog."""
    settings = load_settings()
    watchdog = settings.watchdog
    now = time.time()
    queue = fetch_queue_health(db_path)
    critical = queue["drop_ratio"] >= watchdog.queue_drop_ratio_critical
    warning = queue["drop_ratio"] >= watchdog.queue_drop_ratio_warning

    with _readonly(db_path) as conn:
        health_rows = conn.execute(
            """
            SELECT sh.station_id, sh.health_state, sh.enabled, sh.last_chunk_at,
                   sh.restart_count_today, sh.cool_down_until, sh.last_error,
                   s.display_name
            FROM station_health sh
            LEFT JOIN stations s ON s.name = sh.station_id
            ORDER BY sh.station_id
            """
        ).fetchall()
        events = conn.execute(
            """
            SELECT station_id, event_type, old_state, new_state, reason,
                   action_taken, created_at
            FROM station_recovery_events
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()

    stations: list[dict] = []
    counts = {"active": 0, "healthy": 0, "stale": 0, "disabled": 0}
    for row in health_rows:
        item = dict(row)
        last_chunk_at = item.get("last_chunk_at")
        age_seconds = None
        if last_chunk_at:
            try:
                parsed = datetime.fromisoformat(str(last_chunk_at))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                age_seconds = max(now - parsed.timestamp(), 0.0)
            except ValueError:
                age_seconds = None
        item["age_seconds"] = age_seconds
        enabled = bool(item.get("enabled"))
        state = item.get("health_state") or "unknown"
        if enabled:
            counts["active"] += 1
            if state == "healthy":
                counts["healthy"] += 1
            elif state == "stale":
                counts["stale"] += 1
        else:
            counts["disabled"] += 1
        stations.append(item)

    return {
        "target_active_stations": watchdog.target_active_stations,
        "counts": counts,
        "stations": stations,
        "events": [dict(row) for row in events],
        "queue": queue,
        "queue_critical": critical,
        "queue_warning": warning,
        "watchdog_enabled": watchdog.enabled,
        "stale_after_minutes": watchdog.station_stale_after_minutes,
    }


@dataclass(frozen=True)
class HitAdvertiserRow:
    id: int
    canonical_name: str
    normalized_name: str
    vertical: str
    domain: str | None
    source_type: str
    confidence: str
    status: str
    trademark_entity_id: int | None
    evidence_path: str | None
    detection_count: int
    station_count: int
    updated_at: float


@dataclass(frozen=True)
class HitAdvertiserDetectionRow:
    id: int
    detection_id: int
    station_display_name: str
    market: str | None
    hit_ts: float
    website: str | None
    phone_number: str | None
    cta: str | None
    offer_summary: str | None
    key_claims: tuple[str, ...]
    confidence: float | None
    audio_clip_path: str | None
    audio_clip_start_sec: float | None
    audio_clip_end_sec: float | None
    transcript: str | None


@dataclass(frozen=True)
class TrademarkKeywordRow:
    id: int
    trademark_entity_id: int
    entity_name: str
    keyword: str
    variant_type: str
    source_type: str
    status: str
    verification_status: str | None
    trademark_risk: str | None
    ad_copy_allowed: bool
    landing_page_allowed: bool
    confidence: float | None


def advertiser_entities_available(db_path: Path) -> bool:
    if not db_exists(db_path):
        return False
    with _readonly(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='advertiser_entities'"
        ).fetchone()
        return row is not None


def trademark_tables_available(db_path: Path) -> bool:
    if not db_exists(db_path):
        return False
    with _readonly(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='trademark_keyword_candidates'"
        ).fetchone()
        return row is not None


def fetch_hit_advertisers(db_path: Path, *, limit: int = 100) -> list[HitAdvertiserRow]:
    if not advertiser_entities_available(db_path):
        return []
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ae.id, ae.canonical_name, ae.normalized_name, ae.vertical, ae.domain,
                   ae.source_type, ae.confidence, ae.status, ae.trademark_entity_id,
                   ae.evidence_path, ae.updated_at,
                   COUNT(DISTINCT aed.id) AS detection_count,
                   COUNT(DISTINCT aed.station_id) AS station_count
            FROM advertiser_entities ae
            LEFT JOIN advertiser_entity_detections aed ON aed.advertiser_entity_id = ae.id
            GROUP BY ae.id
            ORDER BY ae.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        HitAdvertiserRow(
            id=int(row["id"]),
            canonical_name=str(row["canonical_name"]),
            normalized_name=str(row["normalized_name"]),
            vertical=str(row["vertical"]),
            domain=row["domain"],
            source_type=str(row["source_type"]),
            confidence=str(row["confidence"]),
            status=str(row["status"]),
            trademark_entity_id=int(row["trademark_entity_id"])
            if row["trademark_entity_id"] is not None
            else None,
            evidence_path=row["evidence_path"],
            detection_count=int(row["detection_count"]),
            station_count=int(row["station_count"]),
            updated_at=float(row["updated_at"]),
        )
        for row in rows
    ]


def fetch_hit_advertiser_detail(
    db_path: Path, advertiser_id: int
) -> tuple[HitAdvertiserRow | None, list[HitAdvertiserDetectionRow]]:
    if not advertiser_entities_available(db_path):
        return None, []
    with _readonly(db_path) as conn:
        header = conn.execute(
            """
            SELECT ae.id, ae.canonical_name, ae.normalized_name, ae.vertical, ae.domain,
                   ae.source_type, ae.confidence, ae.status, ae.trademark_entity_id,
                   ae.evidence_path, ae.updated_at,
                   COUNT(DISTINCT aed.id) AS detection_count,
                   COUNT(DISTINCT aed.station_id) AS station_count
            FROM advertiser_entities ae
            LEFT JOIN advertiser_entity_detections aed ON aed.advertiser_entity_id = ae.id
            WHERE ae.id = ?
            GROUP BY ae.id
            """,
            (advertiser_id,),
        ).fetchone()
        if header is None:
            return None, []
        detections = conn.execute(
            """
            SELECT id, detection_id, station_display_name, market, hit_ts, website,
                   phone_number, cta, offer_summary, key_claims, detection_confidence,
                   audio_clip_path, audio_clip_start_sec, audio_clip_end_sec, transcript
            FROM advertiser_entity_detections
            WHERE advertiser_entity_id = ?
            ORDER BY hit_ts
            """,
            (advertiser_id,),
        ).fetchall()

    summary = HitAdvertiserRow(
        id=int(header["id"]),
        canonical_name=str(header["canonical_name"]),
        normalized_name=str(header["normalized_name"]),
        vertical=str(header["vertical"]),
        domain=header["domain"],
        source_type=str(header["source_type"]),
        confidence=str(header["confidence"]),
        status=str(header["status"]),
        trademark_entity_id=int(header["trademark_entity_id"])
        if header["trademark_entity_id"] is not None
        else None,
        evidence_path=header["evidence_path"],
        detection_count=int(header["detection_count"]),
        station_count=int(header["station_count"]),
        updated_at=float(header["updated_at"]),
    )
    detail_rows: list[HitAdvertiserDetectionRow] = []
    for row in detections:
        raw_claims = row["key_claims"] or "[]"
        try:
            claims = tuple(json.loads(raw_claims))
        except json.JSONDecodeError:
            claims = (str(raw_claims),)
        detail_rows.append(
            HitAdvertiserDetectionRow(
                id=int(row["id"]),
                detection_id=int(row["detection_id"]),
                station_display_name=str(row["station_display_name"] or "—"),
                market=row["market"],
                hit_ts=float(row["hit_ts"]),
                website=row["website"],
                phone_number=row["phone_number"],
                cta=row["cta"],
                offer_summary=row["offer_summary"],
                key_claims=claims,
                confidence=float(row["detection_confidence"])
                if row["detection_confidence"] is not None
                else None,
                audio_clip_path=row["audio_clip_path"],
                audio_clip_start_sec=float(row["audio_clip_start_sec"])
                if row["audio_clip_start_sec"] is not None
                else None,
                audio_clip_end_sec=float(row["audio_clip_end_sec"])
                if row["audio_clip_end_sec"] is not None
                else None,
                transcript=row["transcript"],
            )
        )
    return summary, detail_rows


def fetch_trademark_keywords(
    db_path: Path,
    *,
    source_type: str | None = None,
    status: str | None = None,
    limit: int = 300,
) -> list[TrademarkKeywordRow]:
    if not trademark_tables_available(db_path):
        return []
    params: list[object] = []
    clauses = ["1=1"]
    if source_type:
        clauses.append("tk.source_type = ?")
        params.append(source_type)
    if status:
        clauses.append("tk.status = ?")
        params.append(status)
    params.append(limit)
    with _readonly(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(trademark_keyword_candidates)").fetchall()
        }
        verification_select = (
            "tk.verification_status"
            if "verification_status" in columns
            else "'needs_review'"
        )
        risk_select = (
            "tk.trademark_risk" if "trademark_risk" in columns else "'unknown'"
        )
        landing_select = (
            "tk.landing_page_allowed"
            if "landing_page_allowed" in columns
            else "1"
        )
        rows = conn.execute(
            f"""
            SELECT tk.id, tk.trademark_entity_id, te.canonical_name AS entity_name,
                   tk.keyword, tk.variant_type, tk.source_type, tk.status,
                   {verification_select} AS verification_status,
                   {risk_select} AS trademark_risk,
                   tk.ad_copy_allowed, {landing_select} AS landing_page_allowed,
                   tk.confidence
            FROM trademark_keyword_candidates tk
            JOIN trademark_entities te ON te.id = tk.trademark_entity_id
            WHERE {' AND '.join(clauses)}
            ORDER BY te.canonical_name, tk.keyword
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [
        TrademarkKeywordRow(
            id=int(row["id"]),
            trademark_entity_id=int(row["trademark_entity_id"]),
            entity_name=str(row["entity_name"]),
            keyword=str(row["keyword"]),
            variant_type=str(row["variant_type"]),
            source_type=str(row["source_type"]),
            status=str(row["status"]),
            verification_status=row["verification_status"],
            trademark_risk=row["trademark_risk"],
            ad_copy_allowed=bool(row["ad_copy_allowed"]),
            landing_page_allowed=bool(row["landing_page_allowed"]),
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
        )
        for row in rows
    ]


@contextmanager
def _readonly(db_path: Path):
    connection = get_connection(db_path, read_only=True)
    try:
        yield connection
    finally:
        connection.close()
