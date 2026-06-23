"""JSON API helpers for the RadioSense operational dashboard."""

from __future__ import annotations

import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dashboard import harvest_api, queries
from shared.config import load_stations
from shared.db import get_connection, migrate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = PROJECT_ROOT / "exports"
SAFE_EXPORT_EXTENSIONS = {".csv", ".json", ".jsonl", ".md", ".txt"}


def _iso_ts(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"
        except ValueError:
            return text
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"
    return str(value)


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"


def _readonly_counts_24h(db_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    since = time.time() - 24 * 3600
    detections: dict[str, int] = {}
    keyword_hits: dict[str, int] = {}
    if not queries.db_exists(db_path):
        return detections, keyword_hits
    conn = get_connection(db_path, read_only=True)
    try:
        for row in conn.execute(
            """
            SELECT s.name AS station_name, COUNT(*) AS cnt
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            JOIN stations s ON s.id = c.station_id
            WHERE c.start_ts >= ?
            GROUP BY s.name
            """,
            (since,),
        ):
            detections[str(row["station_name"])] = int(row["cnt"])
        for row in conn.execute(
            """
            SELECT s.name AS station_name, COUNT(*) AS cnt
            FROM keyword_hits kh
            JOIN stations s ON s.id = kh.station_id
            WHERE kh.hit_ts >= ?
            GROUP BY s.name
            """,
            (since,),
        ):
            keyword_hits[str(row["station_name"])] = int(row["cnt"])
    except Exception:
        pass
    finally:
        conn.close()
    return detections, keyword_hits


def fetch_overview_json(db_path: Path) -> dict[str, Any]:
    health = queries.fetch_health(db_path)
    queue = queries.fetch_queue_health(db_path) if queries.db_exists(db_path) else {}
    harvest = harvest_api.fetch_harvest_status(db_path) if queries.db_exists(db_path) else {}
    running = bool(harvest.get("running"))

    station_counts = {"total": 0, "enabled": 0, "live": 0, "stale": 0, "down": 0}
    detections_total = int(harvest.get("detections_total") or 0)
    last_24h = 0
    latest_at: str | None = None

    if queries.db_exists(db_path):
        stations_payload = fetch_stations_json(db_path, limit=500)
        for row in stations_payload["rows"]:
            station_counts["total"] += 1
            if row.get("enabled"):
                station_counts["enabled"] += 1
            status = str(row.get("status") or "disabled")
            if status in station_counts:
                station_counts[status] += 1

        overview = queries.fetch_overview(db_path)
        detections_total = max(detections_total, overview.detections_today)
        last_24h = overview.detections_today
        conn = get_connection(db_path, read_only=True)
        try:
            row = conn.execute(
                """
                SELECT MAX(c.start_ts) AS latest
                FROM detections d
                JOIN chunks c ON c.id = d.chunk_id
                """
            ).fetchone()
            latest_at = _iso_ts(row["latest"] if row else None)
        except Exception:
            latest_at = None
        finally:
            conn.close()

    yaml_stations = harvest_api.fetch_station_config()
    if station_counts["total"] == 0 and yaml_stations:
        station_counts["total"] = len(yaml_stations)
        station_counts["enabled"] = sum(1 for s in yaml_stations if s.get("enabled"))

    return {
        "status": "ok" if health.get("db_reachable") else "error",
        "db_reachable": bool(health.get("db_reachable")),
        "generated_at": _now_iso(),
        "stations": station_counts,
        "queue": {
            "pending": int(queue.get("pending") or health.get("pending_count") or 0),
            "processing": 0,
            "done": int(queue.get("done") or 0),
            "dropped": int(queue.get("dropped") or 0),
            "drop_ratio": float(queue.get("drop_ratio") or 0),
            "drop_warning": bool(queue.get("drop_warning")),
        },
        "detections": {
            "total": detections_total,
            "last_24h": last_24h,
            "latest_at": latest_at,
        },
        "harvest": {
            "running": running,
            "status": "running" if running else "stopped",
            "profile": harvest.get("profile"),
        },
    }


def fetch_stations_json(
    db_path: Path,
    *,
    enabled: str = "all",
    status: str = "all",
    limit: int = 100,
) -> dict[str, Any]:
    db_rows = {str(r["name"]): r for r in queries.fetch_stations(db_path)} if queries.db_exists(db_path) else {}
    det_24h, kw_24h = _readonly_counts_24h(db_path)
    yaml_cfg = {str(s["station_id"]): s for s in harvest_api.fetch_station_config()}
    names = sorted(set(yaml_cfg) | set(db_rows))

    rows: list[dict[str, Any]] = []
    for name in names:
        cfg = yaml_cfg.get(name, {})
        db = db_rows.get(name, {})
        is_enabled = bool(cfg.get("enabled", db.get("enabled", False)))
        row_status = str(db.get("status") or ("disabled" if not is_enabled else "waiting"))

        if enabled == "true" and not is_enabled:
            continue
        if enabled == "false" and is_enabled:
            continue
        if status != "all" and row_status != status:
            continue

        last_ts = db.get("last_chunk_ts")
        rows.append(
            {
                "id": name,
                "station_id": name,
                "name": name,
                "display_name": cfg.get("display_name") or db.get("display_name") or name,
                "market": cfg.get("market") or "",
                "state": cfg.get("state"),
                "enabled": is_enabled,
                "stream_url": cfg.get("stream_url") or db.get("url"),
                "format": cfg.get("format"),
                "status": row_status,
                "last_chunk_at": _iso_ts(last_ts),
                "chunk_age_seconds": db.get("age_seconds"),
                "detections_24h": det_24h.get(name, 0),
                "keyword_hits_24h": kw_24h.get(name, 0),
                "last_error": db.get("last_error"),
            }
        )

    limit = max(1, min(limit, 500))
    return {"rows": rows[:limit], "count": len(rows)}


def fetch_detections_json(
    db_path: Path,
    *,
    limit: int = 100,
    offset: int = 0,
    station: str | None = None,
    since: str | None = None,
    q: str | None = None,
    min_confidence: float | None = None,
) -> dict[str, Any]:
    if not queries.db_exists(db_path):
        return {"rows": [], "count": 0, "limit": limit, "offset": offset}

    clauses = ["1=1"]
    params: list[object] = []

    if station:
        clauses.append("s.name = ?")
        params.append(station)
    if since:
        try:
            parsed = datetime.fromisoformat(since.replace("Z", "+00:00"))
            since_ts = parsed.timestamp()
            clauses.append("c.start_ts >= ?")
            params.append(since_ts)
        except ValueError:
            pass
    if min_confidence is not None:
        clauses.append("d.confidence >= ?")
        params.append(min_confidence)
    if q:
        like = f"%{q}%"
        clauses.append(
            "(d.company_name LIKE ? OR d.offer_summary LIKE ? OR t.text LIKE ? OR kh.keywords LIKE ?)"
        )
        params.extend([like, like, like, like])

    where = " AND ".join(clauses)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    conn = get_connection(db_path, read_only=True)
    try:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM detections d
            LEFT JOIN chunks c ON c.id = d.chunk_id
            LEFT JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = c.id
            LEFT JOIN (
                SELECT detection_id, GROUP_CONCAT(keyword, ', ') AS keywords
                FROM keyword_hits WHERE detection_id IS NOT NULL GROUP BY detection_id
            ) kh ON kh.detection_id = d.id
            WHERE {where}
            """,
            tuple(params),
        ).fetchone()[0]

        rows_raw = conn.execute(
            f"""
            SELECT d.id AS detection_id, d.company_name, d.offer_summary, d.confidence,
                   d.is_ad, d.ad_category,
                   c.start_ts, s.name AS station_name, s.display_name AS station_display,
                   t.text AS transcript_text, kh.keywords
            FROM detections d
            LEFT JOIN chunks c ON c.id = d.chunk_id
            LEFT JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = c.id
            LEFT JOIN (
                SELECT detection_id, GROUP_CONCAT(keyword, ', ') AS keywords
                FROM keyword_hits WHERE detection_id IS NOT NULL GROUP BY detection_id
            ) kh ON kh.detection_id = d.id
            WHERE {where}
            ORDER BY d.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    finally:
        conn.close()

    rows: list[dict[str, Any]] = []
    for row in rows_raw:
        snippet = (row["transcript_text"] or "").strip()
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        detected = _iso_ts(row["start_ts"])
        station_name = row["station_name"]
        rows.append(
            {
                "id": int(row["detection_id"]),
                "detection_id": int(row["detection_id"]),
                "station": station_name,
                "station_id": station_name,
                "detected_at": detected,
                "start_ts": detected,
                "company_name": row["company_name"],
                "keyword": row["keywords"],
                "confidence": row["confidence"],
                "is_ad": bool(row["is_ad"]) if row["is_ad"] is not None else None,
                "offer_summary": row["offer_summary"],
                "transcript_snippet": snippet,
                "review_status": "new",
                "audio_url": None,
            }
        )

    return {"rows": rows, "count": int(total), "limit": limit, "offset": offset}


def _trademark_rows(db_path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in queries.fetch_trademark_keywords(db_path, limit=limit):
        rows.append(
            {
                "id": f"trademark-{row.id}",
                "keyword": row.keyword,
                "source": "trademark",
                "score": float(row.confidence or 0.7),
                "entity": row.entity_name,
                "trademark_risk": row.trademark_risk or "unknown",
                "review_status": row.status or "new",
                "first_seen": _now_iso(),
                "last_seen": _now_iso(),
                "ad_copy_allowed": row.ad_copy_allowed,
                "landing_page_allowed": row.landing_page_allowed,
            }
        )
    return rows


def _cfpb_rows(db_path: Path, limit: int) -> list[dict[str, Any]]:
    if not queries.cfpb_tables_available(db_path):
        return []
    rows: list[dict[str, Any]] = []
    for row in queries.fetch_cfpb_candidates(db_path, limit=limit):
        score = float(row.get("score") or 0) / 100.0 if float(row.get("score") or 0) > 1 else float(row.get("score") or 0)
        rows.append(
            {
                "id": f"cfpb-{row['id']}",
                "keyword": row.get("candidate_name") or row.get("normalized_candidate"),
                "source": "cfpb",
                "score": score,
                "entity": row.get("company_raw") or row.get("candidate_name"),
                "trademark_risk": "unknown",
                "review_status": row.get("verification_status") or "new",
                "first_seen": _now_iso(),
                "last_seen": _now_iso(),
                "ad_copy_allowed": False,
                "landing_page_allowed": True,
            }
        )
    return rows


def _live_keyword_rows(db_path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hit in queries.fetch_keyword_hits(db_path, window_days=30, limit=limit):
        rows.append(
            {
                "id": f"live-{hit.id}",
                "keyword": hit.keyword,
                "source": "live",
                "score": 0.75,
                "entity": hit.station_label,
                "trademark_risk": "unknown",
                "review_status": "new",
                "first_seen": _iso_ts(hit.hit_ts),
                "last_seen": _iso_ts(hit.hit_ts),
                "ad_copy_allowed": False,
                "landing_page_allowed": True,
            }
        )
    return rows


def _export_keyword_rows(limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    candidates = [
        EXPORTS_DIR / "keyword_candidates_current.csv",
        EXPORTS_DIR / "overnight_keyword_candidates.csv",
        EXPORTS_DIR / "keyword_candidates_fresh.csv",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for i, row in enumerate(reader):
                    if i >= limit:
                        break
                    keyword = row.get("keyword") or row.get("phrase") or row.get("candidate")
                    if not keyword:
                        continue
                    score_raw = row.get("score") or row.get("confidence") or "0.7"
                    try:
                        score = float(score_raw)
                        if score > 1:
                            score /= 100.0
                    except ValueError:
                        score = 0.7
                    rows.append(
                        {
                            "id": f"export-{path.stem}-{i}",
                            "keyword": keyword,
                            "source": "export",
                            "score": score,
                            "entity": row.get("entity") or row.get("company") or row.get("source"),
                            "trademark_risk": row.get("trademark_risk") or "unknown",
                            "review_status": row.get("review_status") or "new",
                            "first_seen": _now_iso(),
                            "last_seen": _now_iso(),
                            "ad_copy_allowed": False,
                            "landing_page_allowed": True,
                        }
                    )
        except Exception as exc:
            warnings.append(f"Failed parsing {path.name}: {exc}")
    return rows, warnings


def fetch_keyword_candidates_json(
    db_path: Path,
    *,
    source: str = "all",
    status: str | None = None,
    min_score: float | None = None,
    limit: int = 200,
    offset: int = 0,
    q: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 1000))
    warnings: list[str] = []
    combined: list[dict[str, Any]] = []

    source_map = {
        "trademark": lambda: _trademark_rows(db_path, limit),
        "cfpb": lambda: _cfpb_rows(db_path, limit),
        "live": lambda: _live_keyword_rows(db_path, limit),
        "export": lambda: _export_keyword_rows(limit)[0],
        "harvest": lambda: _trademark_rows(db_path, limit),
    }

    if source == "all":
        combined.extend(_trademark_rows(db_path, limit))
        combined.extend(_cfpb_rows(db_path, limit))
        combined.extend(_live_keyword_rows(db_path, limit))
        export_rows, export_warnings = _export_keyword_rows(limit)
        combined.extend(export_rows)
        warnings.extend(export_warnings)
    elif source in source_map:
        if source == "export":
            export_rows, export_warnings = _export_keyword_rows(limit)
            combined.extend(export_rows)
            warnings.extend(export_warnings)
        else:
            combined.extend(source_map[source]())
    else:
        combined.extend(_trademark_rows(db_path, limit))

    if status:
        combined = [r for r in combined if str(r.get("review_status")) == status]
    if min_score is not None:
        combined = [r for r in combined if float(r.get("score") or 0) >= min_score]
    if q:
        q_lower = q.lower()
        combined = [r for r in combined if q_lower in str(r.get("keyword", "")).lower()]

    sources = {
        "trademark": sum(1 for r in combined if r.get("source") == "trademark"),
        "cfpb": sum(1 for r in combined if r.get("source") == "cfpb"),
        "export": sum(1 for r in combined if r.get("source") == "export"),
        "live": sum(1 for r in combined if r.get("source") == "live"),
    }

    offset = max(0, offset)
    page = combined[offset : offset + limit]
    result: dict[str, Any] = {"rows": page, "count": len(combined), "sources": sources}
    if warnings:
        result["warnings"] = warnings
    return result


def _derive_advertisers(db_path: Path, limit: int) -> list[dict[str, Any]]:
    conn = get_connection(db_path, read_only=True)
    try:
        raw = conn.execute(
            """
            SELECT d.company_name AS name,
                   COUNT(*) AS detection_count,
                   MIN(c.start_ts) AS first_seen,
                   MAX(c.start_ts) AS last_seen,
                   GROUP_CONCAT(DISTINCT s.name) AS stations
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            JOIN stations s ON s.id = c.station_id
            WHERE d.company_name IS NOT NULL AND TRIM(d.company_name) != ''
            GROUP BY d.company_name
            ORDER BY detection_count DESC, last_seen DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    rows: list[dict[str, Any]] = []
    for i, row in enumerate(raw, start=1):
        stations = [s for s in str(row["stations"] or "").split(",") if s]
        rows.append(
            {
                "id": i,
                "name": row["name"],
                "canonical_name": row["name"],
                "domain": None,
                "vertical": "unknown",
                "stations": stations,
                "detection_count": int(row["detection_count"]),
                "first_seen": _iso_ts(row["first_seen"]),
                "last_seen": _iso_ts(row["last_seen"]),
                "confidence": "medium",
                "status": "needs_review",
                "source": "derived",
            }
        )
    return rows


def fetch_advertisers_json(
    db_path: Path,
    *,
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    vertical: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    rows: list[dict[str, Any]] = []

    if queries.advertiser_entities_available(db_path):
        migrate(db_path)
        for adv in queries.fetch_hit_advertisers(db_path, limit=limit + offset + 500):
            conn = get_connection(db_path, read_only=True)
            try:
                station_rows = conn.execute(
                    """
                    SELECT DISTINCT station_display_name FROM advertiser_entity_detections
                    WHERE advertiser_entity_id = ?
                    """,
                    (adv.id,),
                ).fetchall()
            finally:
                conn.close()
            stations = [str(r[0]) for r in station_rows if r[0]]
            rows.append(
                {
                    "id": adv.id,
                    "name": adv.canonical_name,
                    "canonical_name": adv.canonical_name,
                    "domain": adv.domain,
                    "vertical": adv.vertical,
                    "stations": stations,
                    "detection_count": adv.detection_count,
                    "first_seen": _iso_ts(adv.updated_at),
                    "last_seen": _iso_ts(adv.updated_at),
                    "confidence": adv.confidence,
                    "status": adv.status,
                    "source": adv.source_type,
                }
            )

    if len(rows) < 5 and queries.db_exists(db_path):
        rows = _derive_advertisers(db_path, limit + offset + 500)

    if status:
        rows = [r for r in rows if str(r.get("status")) == status]
    if vertical:
        rows = [r for r in rows if str(r.get("vertical")) == vertical]
    if q:
        q_lower = q.lower()
        rows = [r for r in rows if q_lower in str(r.get("name", "")).lower()]

    page = rows[offset : offset + limit]
    return {"rows": page, "count": len(rows)}


def fetch_advertiser_detail_json(db_path: Path, advertiser_id: int) -> dict[str, Any] | None:
    if queries.advertiser_entities_available(db_path):
        summary, detections = queries.fetch_hit_advertiser_detail(db_path, advertiser_id)
        if summary is not None:
            return {
                "advertiser": {
                    "id": summary.id,
                    "name": summary.canonical_name,
                    "domain": summary.domain,
                    "vertical": summary.vertical,
                    "status": summary.status,
                    "confidence": summary.confidence,
                },
                "detections": [
                    {
                        "id": d.detection_id,
                        "station": d.station_display_name,
                        "detected_at": _iso_ts(d.hit_ts),
                        "transcript_snippet": d.transcript,
                        "offer_summary": d.offer_summary,
                        "confidence": d.confidence,
                    }
                    for d in detections
                ],
                "keywords": [],
            }

    if not queries.db_exists(db_path):
        return None

    all_derived = _derive_advertisers(db_path, 500)
    match = next((a for a in all_derived if a["id"] == advertiser_id), None)
    if match is None:
        return None

    name = match["name"]
    dets = fetch_detections_json(db_path, limit=50, q=name)
    filtered = [d for d in dets["rows"] if d.get("company_name") == name]
    return {
        "advertiser": {
            "id": match["id"],
            "name": match["name"],
            "domain": match.get("domain"),
            "vertical": match.get("vertical"),
            "status": match.get("status"),
            "confidence": match.get("confidence"),
        },
        "detections": filtered,
        "keywords": [],
    }


def _human_size(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.0f} KB"
    return f"{num / (1024 * 1024):.1f} MB"


def _count_file_rows(path: Path) -> int | None:
    ext = path.suffix.lower()
    try:
        if ext == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                return max(sum(1 for _ in csv.reader(handle)) - 1, 0)
        if ext == ".jsonl":
            with path.open(encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        if ext in {".md", ".txt"}:
            with path.open(encoding="utf-8") as handle:
                return sum(1 for _ in handle)
    except OSError:
        return None
    return None


def _export_purpose(filename: str) -> str:
    lower = filename.lower()
    if "keyword" in lower:
        return "Keyword candidate export"
    if "station" in lower:
        return "Station configuration or performance export"
    if "loan" in lower:
        return "Loan vertical research export"
    return "Pipeline export file"


def fetch_exports_json() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if not EXPORTS_DIR.is_dir():
        return {"rows": [], "count": 0}

    for path in sorted(EXPORTS_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SAFE_EXPORT_EXTENSIONS:
            continue
        stat = path.stat()
        rows.append(
            {
                "filename": path.name,
                "type": path.suffix.lstrip(".").upper(),
                "rows": _count_file_rows(path),
                "size": _human_size(stat.st_size),
                "size_bytes": stat.st_size,
                "last_modified": _iso_ts(stat.st_mtime),
                "purpose": _export_purpose(path.name),
                "download_url": f"/api/exports/{path.name}",
            }
        )

    return {"rows": rows, "count": len(rows)}


def resolve_export_path(filename: str) -> Path | None:
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        return None
    if Path(safe).suffix.lower() not in SAFE_EXPORT_EXTENSIONS:
        return None
    candidate = (EXPORTS_DIR / safe).resolve()
    try:
        candidate.relative_to(EXPORTS_DIR.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def export_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".csv":
        return "text/csv"
    if ext == ".jsonl":
        return "application/x-ndjson"
    if ext == ".json":
        return "application/json"
    return "text/plain"


def fetch_watchdog_json(db_path: Path) -> dict[str, Any]:
    if not queries.db_exists(db_path):
        return {"station_health": [], "recovery_events": [], "commands": []}
    if not queries.watchdog_tables_available(db_path):
        migrate(db_path)

    overview = queries.fetch_watchdog_overview(db_path)
    station_health = [
        {
            "station_id": row.get("station_id"),
            "health_state": row.get("health_state"),
            "last_chunk_at": row.get("last_chunk_at"),
            "last_error": row.get("last_error"),
            "consecutive_failures": row.get("restart_count_today") or 0,
        }
        for row in overview.get("stations", [])
    ]
    recovery_events = [
        {
            "id": i + 1,
            "station_id": ev.get("station_id"),
            "event_type": ev.get("event_type"),
            "old_state": ev.get("old_state"),
            "new_state": ev.get("new_state"),
            "action_taken": ev.get("action_taken"),
            "created_at": _iso_ts(ev.get("created_at")),
        }
        for i, ev in enumerate(overview.get("events", []))
    ]

    commands: list[dict[str, Any]] = []
    if queries.control_commands_available(db_path):
        conn = get_connection(db_path, read_only=True)
        try:
            for row in conn.execute(
                """
                SELECT id, station_id, command, reason, status, created_at
                FROM station_control_commands
                ORDER BY id DESC LIMIT 20
                """
            ):
                commands.append(
                    {
                        "id": int(row["id"]),
                        "station_id": row["station_id"],
                        "command": row["command"],
                        "reason": row["reason"],
                        "status": row["status"],
                        "created_at": _iso_ts(row["created_at"]),
                    }
                )
        except Exception:
            pass
        finally:
            conn.close()

    return {
        "station_health": station_health,
        "recovery_events": recovery_events,
        "commands": commands,
    }


def build_live_event(db_path: Path) -> dict[str, Any]:
    overview = fetch_overview_json(db_path)
    latest = fetch_detections_json(db_path, limit=5)
    alerts: list[dict[str, str]] = []
    if overview["queue"].get("drop_warning"):
        alerts.append({"level": "warn", "message": "Drop ratio high"})
    if overview["stations"].get("down", 0) > 0:
        alerts.append(
            {
                "level": "error",
                "message": f"{overview['stations']['down']} station(s) down",
            }
        )
    if overview["stations"].get("stale", 0) > 0:
        alerts.append(
            {
                "level": "warn",
                "message": f"{overview['stations']['stale']} station(s) stale",
            }
        )

    return {
        "ts": _now_iso(),
        "health": {
            "status": overview["status"],
            "db_reachable": overview["db_reachable"],
        },
        "queue": overview["queue"],
        "stations": overview["stations"],
        "latest_detections": latest["rows"],
        "alerts": alerts,
    }
