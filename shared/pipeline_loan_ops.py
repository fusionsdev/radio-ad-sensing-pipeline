"""Loan-only pipeline ops report — live Docker DB + strict loan classifier."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Final 48h loan batch — enabled stations (stable slugs in stations.yaml)
FINAL_BATCH_ENABLED: tuple[str, ...] = (
    "ktrh-am-740",
    "klif-am-570",
    "wsb-am-750",
    "wbap-am-820",
    "klbj-am-590",
    "wlw-700",
    "knth-1070",
    "ktsa-550",
    "wfla-970",
    "kabc-am-790",
)

FINAL_BATCH_PAUSED: tuple[str, ...] = (
    "woai-am-1200",
    "wwtn-fm-997",
    "whbo-1040",
    "wibc-fm-931",
    "wtam-am-1100",
    "wgul-860",
)

MEDICAL_LOAN_PATTERNS: tuple[str, ...] = (
    "medical financing",
    "dental financing",
    "vet financing",
    "veterinary financing",
    "healthcare financing",
    "carecredit",
    "care credit",
)

STALE_CHUNK_SEC = 30 * 60
EMPTY_CHUNK_LOOP_MIN = 3
EMPTY_CHUNK_LOOP_WINDOW_SEC = 3600

NOISE_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tax_relief", ("tax", "irs", "tax relief", "tax debt", "tax resolution")),
    ("insurance", ("insurance", "life insurance", "term life", "medicare", "ethos")),
    ("legal", ("attorney", "lawyer", "law firm", "lawsuit", "class action", "injury")),
    (
        "car/home financing",
        ("auto financing", "car financing", "vehicle financing", "roofing", "hvac", "home improvement"),
    ),
    (
        "supplements/jobs/retail",
        ("supplement", "vitamin", "ziprecruiter", "hiring", "job search", "mattress", "furniture"),
    ),
)


@dataclass(frozen=True)
class ServiceStatus:
    name: str
    status: str
    note: str = ""


@dataclass(frozen=True)
class LoanOpsReport:
    generated_at: float
    db_path: str
    latest_chunk_ts: float | None
    latest_detection_ts: float | None
    source_stale: bool
    services: tuple[ServiceStatus, ...]
    markdown: str

    @property
    def action_needed(self) -> str:
        for line in self.markdown.splitlines():
            if line.startswith("**Action:**"):
                return line.replace("**Action:**", "").strip()
        return "no_action"


def _classify_loan(*, company: str = "", offer: str = "", text: str = "") -> dict[str, Any]:
    import importlib.util

    root = Path(__file__).resolve().parent.parent
    candidates = (
        root / "scripts" / "loan_classifier.py",
        Path("/tmp/loan_classifier.py"),
    )
    classify_loan = None
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("loan_classifier", path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        classify_loan = mod.classify_loan
        break
    if classify_loan is None:
        raise ImportError("loan_classifier.py not found (copy to /tmp/loan_classifier.py in container)")

    result = classify_loan(company=company, offer=offer, text=text)
    if not result["is_loan"]:
        combined = f"{company} {offer} {text}".lower()
        for pattern in MEDICAL_LOAN_PATTERNS:
            if pattern in combined:
                return {
                    "classification": "true_loan",
                    "is_loan": True,
                    "matched_positive": [pattern],
                    "matched_negative": None,
                    "reason": f"Medical/vet financing phrase: '{pattern}'",
                }
    return result


def _int(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def _one_float(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> float | None:
    row = conn.execute(sql, params).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0])


def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_age_min(ts: float | None, now: float) -> str:
    if ts is None:
        return "never"
    age = (now - ts) / 60
    if age < 60:
        return f"{age:.0f}m ago"
    return f"{age / 60:.1f}h ago"


def _station_decision(unique_loan: int, true_loan_ads: int, runtime_hours: float, chunks_1h: int) -> tuple[str, str]:
    if chunks_1h == 0 and runtime_hours >= 2:
        return "rotate", "No chunks in last 1h — stream likely dead"
    if unique_loan >= 2:
        return "keep", f"{unique_loan} unique loan advertisers, {true_loan_ads} true loan ads"
    if unique_loan == 1:
        return "watch", "Single loan advertiser — monitor 24-48h"
    if runtime_hours >= 24 and true_loan_ads == 0:
        return "rotate", f"0 true loan ads after {runtime_hours:.0f}h runtime"
    if runtime_hours >= 6 and true_loan_ads == 0 and chunks_1h > 0:
        return "watch", "Ingest OK but no loan signal yet"
    if true_loan_ads == 0:
        return "watch", "Early runtime — insufficient loan data"
    return "keep", "Loan signal present"


def _resolve_action(
    *,
    source_stale: bool,
    services_down: bool,
    empty_chunk_stations: list[str],
    fix_stream_stations: list[str],
    rotate_stations: list[str],
    new_candidates: int,
    pending: int,
    done_1h: int,
) -> str:
    if source_stale:
        return "source_stale_warning"
    if services_down:
        return "pipeline_problem"
    if empty_chunk_stations or fix_stream_stations:
        return "fix_stream"
    if rotate_stations:
        return "rotate_station"
    if new_candidates > 0:
        return "review_new_loan_candidate"
    if pending > 5000 and done_1h < 30:
        return "pipeline_problem"
    return "no_action"


def _fetch_detections(conn: sqlite3.Connection, since_ts: float) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(
        conn.execute(
            """
            SELECT
                d.id AS detection_id,
                d.company_name,
                d.offer_summary,
                d.key_claims,
                d.ad_category,
                c.start_ts,
                s.name AS station,
                t.text
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
            WHERE d.is_ad = 1 AND c.start_ts >= ?
            ORDER BY c.start_ts DESC
            """,
            (since_ts,),
        ).fetchall()
    )


def _classify_detection_row(row: sqlite3.Row) -> dict[str, Any]:
    company = (row["company_name"] or "").strip()
    offer = " ".join(
        part for part in ((row["offer_summary"] or ""), (row["key_claims"] or "")) if part
    ).strip()
    text = (row["text"] or "")[:500]
    return _classify_loan(company=company, offer=offer, text=text)


def _noise_bucket(combined: str, ad_category: str | None) -> str | None:
    blob = f"{combined} {(ad_category or '').lower()}"
    for bucket, patterns in NOISE_CATEGORIES:
        if any(p in blob for p in patterns):
            return bucket
    return None


def build_loan_ops_report(
    conn: sqlite3.Connection,
    *,
    db_path: str = "/app/data/pipeline.db",
    now_ts: float | None = None,
    services: tuple[ServiceStatus, ...] | None = None,
) -> LoanOpsReport:
    """Build the loan-only ops markdown report from a live pipeline DB connection."""
    now = now_ts if now_ts is not None else time.time()
    services = services or ()

    latest_chunk_ts = _one_float(conn, "SELECT MAX(end_ts) FROM chunks WHERE status = 'done'")
    latest_detection_ts = _one_float(
        conn,
        """
        SELECT MAX(c.start_ts)
        FROM detections d
        JOIN chunks c ON c.id = d.chunk_id
        WHERE d.is_ad = 1
        """,
    )
    source_stale = latest_chunk_ts is None or (now - latest_chunk_ts) > STALE_CHUNK_SEC

    chunks_by_status = {
        str(row[0]): int(row[1])
        for row in conn.execute("SELECT status, COUNT(*) FROM chunks GROUP BY status").fetchall()
    }
    pending = chunks_by_status.get("pending", 0)
    done_1h = _int(
        conn,
        "SELECT COUNT(*) FROM chunks WHERE status = 'done' AND end_ts >= ?",
        (now - 3600,),
    )
    errors_1h = _int(
        conn,
        "SELECT COUNT(*) FROM chunks WHERE status = 'dropped' AND end_ts >= ?",
        (now - 3600,),
    )
    stale_chunks = _int(
        conn,
        """
        SELECT COUNT(*) FROM chunks
        WHERE status = 'pending' AND start_ts < ?
        """,
        (now - 7200,),
    )

    station_rows = conn.execute(
        "SELECT id, name, enabled FROM stations ORDER BY name"
    ).fetchall()
    station_by_name = {str(r[1]): (int(r[0]), bool(r[2])) for r in station_rows}

    detections_24h = _fetch_detections(conn, now - 86400)
    classified_24h = [(row, _classify_detection_row(row)) for row in detections_24h]

    def window_stats(hours: float) -> tuple[int, int, int]:
        since = now - (hours * 3600)
        true_loan = 0
        advertisers: set[str] = set()
        keywords: set[str] = set()
        for row, result in classified_24h:
            if float(row["start_ts"]) < since:
                continue
            if result["classification"] != "true_loan":
                continue
            true_loan += 1
            company = (row["company_name"] or "").strip()
            if company:
                advertisers.add(company.lower())
            for pat in result.get("matched_positive") or []:
                keywords.add(pat)
        return true_loan, len(advertisers), len(keywords)

    loan_1h, adv_1h, kw_1h = window_stats(1)
    loan_6h, adv_6h, kw_6h = window_stats(6)
    loan_24h, adv_24h, kw_24h = window_stats(24)

    noise_counts = {name: 0 for name, _ in NOISE_CATEGORIES}
    for row, result in classified_24h:
        if result["classification"] == "true_loan":
            continue
        combined = " ".join(
            filter(
                None,
                [
                    row["company_name"] or "",
                    row["offer_summary"] or "",
                    row["key_claims"] or "",
                    (row["text"] or "")[:300],
                ],
            )
        ).lower()
        bucket = _noise_bucket(combined, row["ad_category"])
        if bucket:
            noise_counts[bucket] += 1
        elif result["classification"] == "excluded_noise":
            for neg in result.get("matched_negative") or []:
                for bucket_name, patterns in NOISE_CATEGORIES:
                    if neg in patterns or any(neg in p for p in patterns):
                        noise_counts[bucket_name] += 1
                        break

    station_health: list[dict[str, Any]] = []
    station_decisions: list[dict[str, Any]] = []
    empty_chunk_stations: list[str] = []
    fix_stream_stations: list[str] = []
    rotate_stations: list[str] = []

    for slug in FINAL_BATCH_ENABLED:
        sid_enabled = station_by_name.get(slug)
        if sid_enabled is None:
            station_health.append(
                {
                    "station": slug,
                    "enabled": False,
                    "runtime_hours": 0,
                    "latest_chunk": None,
                    "chunks_1h": 0,
                    "transcript_ok": "no",
                    "empty_chunk_loop": "unknown",
                    "status": "missing_from_db",
                }
            )
            station_decisions.append(
                {
                    "station": slug,
                    "runtime_hours": 0,
                    "true_loan_ads": 0,
                    "unique_loan_advertisers": 0,
                    "decision": "fix_stream",
                    "reason": "Station slug not in DB — check stations.yaml vs ingestor",
                }
            )
            fix_stream_stations.append(slug)
            continue

        sid, enabled = sid_enabled
        first_ts = _one_float(conn, "SELECT MIN(start_ts) FROM chunks WHERE station_id = ?", (sid,))
        runtime_hours = ((now - first_ts) / 3600) if first_ts else 0.0
        latest_chunk = _one_float(
            conn,
            "SELECT MAX(end_ts) FROM chunks WHERE station_id = ? AND status = 'done'",
            (sid,),
        )
        chunks_1h = _int(
            conn,
            """
            SELECT COUNT(*) FROM chunks
            WHERE station_id = ? AND status = 'done' AND end_ts >= ?
            """,
            (sid, now - 3600),
        )
        recent_done = conn.execute(
            """
            SELECT c.id, t.text IS NOT NULL AND LENGTH(TRIM(t.text)) > 0 AS has_text
            FROM chunks c
            LEFT JOIN transcripts t ON t.chunk_id = c.id
            WHERE c.station_id = ? AND c.status = 'done'
            ORDER BY c.end_ts DESC
            LIMIT 10
            """,
            (sid,),
        ).fetchall()
        transcript_ok = "yes" if recent_done and all(r[1] for r in recent_done) else (
            "partial" if recent_done and any(r[1] for r in recent_done) else "no"
        )
        empty_gaps = _int(
            conn,
            """
            SELECT COUNT(*) FROM gaps
            WHERE station_id = ? AND reason = 'empty_chunk' AND start_ts >= ?
            """,
            (sid, now - EMPTY_CHUNK_LOOP_WINDOW_SEC),
        )
        empty_loop = "yes" if empty_gaps >= EMPTY_CHUNK_LOOP_MIN else "no"
        if empty_loop == "yes":
            empty_chunk_stations.append(slug)

        if not enabled:
            status = "disabled_in_db"
            station_decisions.append(
                {
                    "station": slug,
                    "runtime_hours": round(runtime_hours, 1),
                    "true_loan_ads": 0,
                    "unique_loan_advertisers": 0,
                    "decision": "fix_stream",
                    "reason": "Enabled in batch plan but disabled in DB — restart ingestor after stations.yaml sync",
                }
            )
            station_health.append(
                {
                    "station": slug,
                    "enabled": enabled,
                    "runtime_hours": round(runtime_hours, 1),
                    "latest_chunk": latest_chunk,
                    "chunks_1h": chunks_1h,
                    "transcript_ok": transcript_ok,
                    "empty_chunk_loop": empty_loop,
                    "status": status,
                }
            )
            fix_stream_stations.append(slug)
            continue
        elif latest_chunk is None:
            status = "no_chunks"
        elif (now - latest_chunk) > STALE_CHUNK_SEC:
            status = "stale"
        elif empty_loop == "yes":
            status = "empty_chunk_loop"
        elif chunks_1h == 0:
            status = "idle"
        else:
            status = "ok"

        station_health.append(
            {
                "station": slug,
                "enabled": enabled,
                "runtime_hours": round(runtime_hours, 1),
                "latest_chunk": latest_chunk,
                "chunks_1h": chunks_1h,
                "transcript_ok": transcript_ok,
                "empty_chunk_loop": empty_loop,
                "status": status,
            }
        )

        true_loan_station = 0
        loan_advertisers: set[str] = set()
        if not source_stale:
            for row, result in classified_24h:
                if row["station"] != slug or result["classification"] != "true_loan":
                    continue
                true_loan_station += 1
                company = (row["company_name"] or "").strip()
                if company:
                    loan_advertisers.add(company.lower())

        decision, reason = _station_decision(
            len(loan_advertisers),
            true_loan_station,
            runtime_hours,
            chunks_1h,
        )
        if decision == "rotate":
            rotate_stations.append(slug)
        station_decisions.append(
            {
                "station": slug,
                "runtime_hours": round(runtime_hours, 1),
                "true_loan_ads": true_loan_station,
                "unique_loan_advertisers": len(loan_advertisers),
                "decision": decision,
                "reason": reason,
            }
        )

    new_candidates: list[dict[str, str]] = []
    if not source_stale:
        seen_companies: set[str] = set()
        for row, result in classified_24h:
            if float(row["start_ts"]) < now - 3600:
                continue
            if result["classification"] != "true_loan":
                continue
            company = (row["company_name"] or "").strip() or "(unnamed)"
            key = company.lower()
            if key in seen_companies:
                continue
            seen_companies.add(key)
            evidence = (row["offer_summary"] or row["key_claims"] or (row["text"] or "")[:120]).strip()
            new_candidates.append(
                {
                    "company": company,
                    "station": str(row["station"]),
                    "evidence": evidence[:100],
                    "classifier_result": result["classification"],
                    "suggested_action": "monitor",
                }
            )
            if len(new_candidates) >= 10:
                break

    services_down = any(
        s.name in ("ingestor", "worker", "alerter", "dashboard")
        and "up" not in s.status.lower()
        for s in services
    )
    action = _resolve_action(
        source_stale=source_stale,
        services_down=services_down,
        empty_chunk_stations=empty_chunk_stations,
        fix_stream_stations=fix_stream_stations,
        rotate_stations=rotate_stations,
        new_candidates=len(new_candidates),
        pending=pending,
        done_1h=done_1h,
    )

    live_db = "STALE" if source_stale else "FRESH"
    source_status = (
        "STALE SOURCE WARNING - not reporting keyword conclusions."
        if source_stale
        else "live Docker DB (/app/data/pipeline.db via radio-worker)"
    )

    lines: list[str] = [
        "# Pipeline Ops — Loan-Only Status",
        f"Time: {_fmt_ts(now)}",
        f"Live DB: {live_db} ({db_path})",
        f"Latest chunk: {_fmt_ts(latest_chunk_ts)} ({_fmt_age_min(latest_chunk_ts, now)})",
        f"Latest detection: {_fmt_ts(latest_detection_ts)} ({_fmt_age_min(latest_detection_ts, now)})",
        f"Source status: {source_status}",
        "",
        "## 1. System Health",
        "| service | status | note |",
        "|---|---|---|",
    ]

    default_services = ("ingestor", "worker", "alerter", "dashboard")
    service_map = {s.name: s for s in services}
    for name in default_services:
        svc = service_map.get(name)
        if svc:
            lines.append(f"| {name} | {svc.status} | {svc.note} |")
        else:
            lines.append(f"| {name} | unknown | not probed (run from host wrapper) |")

    lines.extend(
        [
            "",
            "## 2. Queue Health",
            "| metric | value |",
            "|---|---:|",
            f"| pending | {pending} |",
            f"| done last 1h | {done_1h} |",
            f"| errors last 1h | {errors_1h} |",
            f"| stale chunks | {stale_chunks} |",
            "",
            "## 3. Station Health",
            "| station | enabled | runtime_hours | latest_chunk | chunks_1h | transcript_ok | empty_chunk_loop | status |",
            "|---|---|---:|---|---:|---|---|---|",
        ]
    )

    for sh in station_health:
        lines.append(
            f"| {sh['station']} | {sh['enabled']} | {sh['runtime_hours']} | "
            f"{_fmt_age_min(sh['latest_chunk'], now)} | {sh['chunks_1h']} | "
            f"{sh['transcript_ok']} | {sh['empty_chunk_loop']} | {sh['status']} |"
        )

    lines.extend(
        [
            "",
            "## 4. Loan Signal",
            "| window | true_loan_ads | unique_loan_advertisers | new_keywords |",
            "|---|---:|---:|---:|",
        ]
    )

    if source_stale:
        lines.append("| last 1h | — | — | — |")
        lines.append("| last 6h | — | — | — |")
        lines.append("| last 24h | — | — | — |")
    else:
        lines.append(f"| last 1h | {loan_1h} | {adv_1h} | {kw_1h} |")
        lines.append(f"| last 6h | {loan_6h} | {adv_6h} | {kw_6h} |")
        lines.append(f"| last 24h | {loan_24h} | {adv_24h} | {kw_24h} |")

    lines.extend(
        [
            "",
            "## 5. New Loan Candidates",
            "| company/keyword | station | evidence | classifier_result | suggested_action |",
            "|---|---|---|---|---|",
        ]
    )
    if source_stale or not new_candidates:
        lines.append("| — | — | — | — | — |")
    else:
        for cand in new_candidates:
            lines.append(
                f"| {cand['company']} | {cand['station']} | {cand['evidence']} | "
                f"{cand['classifier_result']} | {cand['suggested_action']} |"
            )

    lines.extend(
        [
            "",
            "## 6. Noise Summary",
            "| category | count_24h | note |",
            "|---|---:|---|",
        ]
    )
    noise_notes = {
        "tax_relief": "archived only",
        "insurance": "archived only",
        "legal": "archived only",
        "car/home financing": "excluded",
        "supplements/jobs/retail": "excluded",
    }
    if source_stale:
        for bucket, _ in NOISE_CATEGORIES:
            lines.append(f"| {bucket} | — | {noise_notes.get(bucket, 'excluded')} |")
    else:
        for bucket, _ in NOISE_CATEGORIES:
            lines.append(f"| {bucket} | {noise_counts[bucket]} | {noise_notes.get(bucket, 'excluded')} |")

    lines.extend(
        [
            "",
            "## 7. Station Decision",
            "| station | runtime_hours | true_loan_ads | unique_loan_advertisers | decision | reason |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for sd in station_decisions:
        loan_ads = "—" if source_stale else str(sd["true_loan_ads"])
        uniq = "—" if source_stale else str(sd["unique_loan_advertisers"])
        lines.append(
            f"| {sd['station']} | {sd['runtime_hours']} | {loan_ads} | {uniq} | "
            f"{sd['decision']} | {sd['reason']} |"
        )

    lines.extend(["", "## 8. Action Needed", "", f"**Action:** {action}", ""])

    markdown = "\n".join(lines)
    return LoanOpsReport(
        generated_at=now,
        db_path=db_path,
        latest_chunk_ts=latest_chunk_ts,
        latest_detection_ts=latest_detection_ts,
        source_stale=source_stale,
        services=services,
        markdown=markdown,
    )
