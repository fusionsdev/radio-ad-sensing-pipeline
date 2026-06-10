"""Read-only SQL queries for the dashboard."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dashboard.stats import compute_yield_pct, derive_review_tier, derive_slot_recommendation
from shared.config import load_settings, load_stations
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


@dataclass(frozen=True)
class CfpbOverview:
    total_complaints: int
    total_entities: int
    total_candidates: int
    last_run_status: str | None
    last_run_finished: str | None


@dataclass(frozen=True)
class CfpbRunRow:
    id: int
    started_at: str | None
    finished_at: str | None
    source_mode: str | None
    records_seen: int
    records_inserted: int
    entities_created: int
    candidates_created: int
    status: str | None
    error_message: str | None


@dataclass(frozen=True)
class CfpbEntityRow:
    id: int
    company_raw: str
    company_normalized: str
    complaint_count: int
    narrative_count: int
    trademark_candidate_score: float
    review_status: str
    states_json: str | None
    product_mix_json: str | None
    trademark_entity_id: int | None
    first_seen_at: str | None
    last_seen_at: str | None


@dataclass(frozen=True)
class CfpbCandidateRow:
    id: int
    candidate_name: str
    normalized_candidate: str
    candidate_type: str
    score: float
    confidence: float
    verification_status: str
    source_product: str | None
    source_state: str | None
    source_complaint_id: str | None
    evidence_text: str | None
    company_raw: str | None
    entity_id: int | None
    trademark_entity_id: int | None


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def cfpb_tables_exist(db_path: Path) -> bool:
    if not db_exists(db_path):
        return False
    with _readonly(db_path) as conn:
        return _table_exists(conn, "cfpb_complaints_raw")


def fetch_cfpb_overview(db_path: Path) -> CfpbOverview:
    if not cfpb_tables_exist(db_path):
        return CfpbOverview(0, 0, 0, None, None)
    with _readonly(db_path) as conn:
        complaints = conn.execute("SELECT COUNT(*) FROM cfpb_complaints_raw").fetchone()[0]
        entities = conn.execute("SELECT COUNT(*) FROM cfpb_company_entities").fetchone()[0]
        candidates = conn.execute("SELECT COUNT(*) FROM cfpb_brand_candidates").fetchone()[0]
        last_run = conn.execute(
            "SELECT status, finished_at FROM cfpb_collection_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return CfpbOverview(
        total_complaints=int(complaints),
        total_entities=int(entities),
        total_candidates=int(candidates),
        last_run_status=str(last_run["status"]) if last_run else None,
        last_run_finished=str(last_run["finished_at"]) if last_run and last_run["finished_at"] else None,
    )


def fetch_cfpb_runs(db_path: Path, *, limit: int = 50) -> list[CfpbRunRow]:
    if not cfpb_tables_exist(db_path):
        return []
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, finished_at, source_mode, records_seen,
                   records_inserted, entities_created, candidates_created,
                   status, error_message
            FROM cfpb_collection_runs
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        CfpbRunRow(
            id=int(r["id"]),
            started_at=r["started_at"],
            finished_at=r["finished_at"],
            source_mode=r["source_mode"],
            records_seen=int(r["records_seen"] or 0),
            records_inserted=int(r["records_inserted"] or 0),
            entities_created=int(r["entities_created"] or 0),
            candidates_created=int(r["candidates_created"] or 0),
            status=r["status"],
            error_message=r["error_message"],
        )
        for r in rows
    ]


def fetch_cfpb_entities(db_path: Path, *, limit: int = 100) -> list[CfpbEntityRow]:
    if not cfpb_tables_exist(db_path):
        return []
    with _readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, company_raw, company_normalized, complaint_count,
                   narrative_count, trademark_candidate_score, review_status,
                   states_json, product_mix_json, trademark_entity_id,
                   first_seen_at, last_seen_at
            FROM cfpb_company_entities
            ORDER BY complaint_count DESC, trademark_candidate_score DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        CfpbEntityRow(
            id=int(r["id"]),
            company_raw=str(r["company_raw"]),
            company_normalized=str(r["company_normalized"]),
            complaint_count=int(r["complaint_count"] or 0),
            narrative_count=int(r["narrative_count"] or 0),
            trademark_candidate_score=float(r["trademark_candidate_score"] or 0),
            review_status=str(r["review_status"] or "new"),
            states_json=r["states_json"],
            product_mix_json=r["product_mix_json"],
            trademark_entity_id=int(r["trademark_entity_id"]) if r["trademark_entity_id"] else None,
            first_seen_at=r["first_seen_at"],
            last_seen_at=r["last_seen_at"],
        )
        for r in rows
    ]


def fetch_cfpb_candidates(
    db_path: Path, *, limit: int = 200, min_score: float | None = None
) -> list[CfpbCandidateRow]:
    if not cfpb_tables_exist(db_path):
        return []
    clauses = ["1=1"]
    params: list[object] = []
    if min_score is not None:
        clauses.append("c.score >= ?")
        params.append(min_score)
    params.append(limit)
    sql = f"""
        SELECT c.id, c.candidate_name, c.normalized_candidate, c.candidate_type,
               c.score, c.confidence, c.verification_status, c.source_product,
               c.source_state, c.source_complaint_id, c.evidence_text,
               e.company_raw, e.id AS entity_id, e.trademark_entity_id
        FROM cfpb_brand_candidates c
        LEFT JOIN cfpb_company_entities e ON e.id = c.cfpb_company_entity_id
        WHERE {" AND ".join(clauses)}
        ORDER BY c.score DESC, c.id DESC
        LIMIT ?
    """
    with _readonly(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        CfpbCandidateRow(
            id=int(r["id"]),
            candidate_name=str(r["candidate_name"]),
            normalized_candidate=str(r["normalized_candidate"]),
            candidate_type=str(r["candidate_type"]),
            score=float(r["score"] or 0),
            confidence=float(r["confidence"] or 0),
            verification_status=str(r["verification_status"] or "needs_verification"),
            source_product=r["source_product"],
            source_state=r["source_state"],
            source_complaint_id=r["source_complaint_id"],
            evidence_text=r["evidence_text"],
            company_raw=r["company_raw"],
            entity_id=int(r["entity_id"]) if r["entity_id"] else None,
            trademark_entity_id=int(r["trademark_entity_id"]) if r["trademark_entity_id"] else None,
        )
        for r in rows
    ]


def fetch_cfpb_candidate_detail(db_path: Path, candidate_id: int) -> CfpbCandidateRow | None:
    if not cfpb_tables_exist(db_path):
        return None
    with _readonly(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.id, c.candidate_name, c.normalized_candidate, c.candidate_type,
                   c.score, c.confidence, c.verification_status, c.source_product,
                   c.source_state, c.source_complaint_id, c.evidence_text,
                   e.company_raw, e.id AS entity_id, e.trademark_entity_id
            FROM cfpb_brand_candidates c
            LEFT JOIN cfpb_company_entities e ON e.id = c.cfpb_company_entity_id
            WHERE c.id = ?
            """,
            (candidate_id,),
        ).fetchone()
    if row is None:
        return None
    return CfpbCandidateRow(
        id=int(row["id"]),
        candidate_name=str(row["candidate_name"]),
        normalized_candidate=str(row["normalized_candidate"]),
        candidate_type=str(row["candidate_type"]),
        score=float(row["score"] or 0),
        confidence=float(row["confidence"] or 0),
        verification_status=str(row["verification_status"] or "needs_verification"),
        source_product=row["source_product"],
        source_state=row["source_state"],
        source_complaint_id=row["source_complaint_id"],
        evidence_text=row["evidence_text"],
        company_raw=row["company_raw"],
        entity_id=int(row["entity_id"]) if row["entity_id"] else None,
        trademark_entity_id=int(row["trademark_entity_id"]) if row["trademark_entity_id"] else None,
    )


def update_cfpb_candidate_status(db_path: Path, candidate_id: int, status: str) -> bool:
    allowed = {"needs_verification", "approved_seed", "rejected_noise"}
    if status not in allowed:
        return False
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "UPDATE cfpb_brand_candidates SET verification_status = ? WHERE id = ?",
            (status, candidate_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_cfpb_entity_status(db_path: Path, entity_id: int, status: str) -> bool:
    allowed = {"new", "needs_verification", "approved_seed", "rejected_noise"}
    if status not in allowed:
        return False
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE cfpb_company_entities
            SET review_status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, entity_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


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
