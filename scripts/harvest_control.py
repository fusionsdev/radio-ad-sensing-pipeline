#!/usr/bin/env python3
"""Harvest control CLI for the Radio Ad Pipeline (Safe Run Mode).

Commands
--------
    probe                                   probe up to N station streams
    start   --profile overnight_keyword_harvest
                                            begin a harvest session
    stop                                    stop a running harvest session
    status                                  show runtime + DB harvest status
    export  [--limit N]                     export keyword candidates (csv/jsonl)
    top     --limit N                       print top keyword candidates
    summary                                 write exports/overnight_keyword_summary.md

Safe Run Mode: this script never edits source, runs migrations, commits, or
deletes data. It only reads the pipeline DB (read-only) and writes to exports/
and runtime/.

Usage:
    python scripts/harvest_control.py probe
    python scripts/harvest_control.py start --profile overnight_keyword_harvest
    python scripts/harvest_control.py stop
    python scripts/harvest_control.py status
    python scripts/harvest_control.py export
    python scripts/harvest_control.py top --limit 50
    python scripts/harvest_control.py summary
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - repo depends on PyYAML
    raise SystemExit("PyYAML is required to run harvest_control.") from exc

# --- paths -----------------------------------------------------------------
# Bootstrap repo root onto sys.path BEFORE importing shared.* so the documented
# invocation `python scripts/harvest_control.py ...` works regardless of cwd
# (matches the convention used by every other script in scripts/).

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.config import CONFIG_DIR, load_settings, load_stations  # noqa: E402
from shared.db import get_connection  # noqa: E402

PROFILES_PATH = CONFIG_DIR / "harvest_profiles.yaml"
EXPORTS_DIR = PROJECT_ROOT / "exports"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
STATUS_FILE = RUNTIME_DIR / "harvest_status.json"

DEFAULT_PROFILE = "overnight_keyword_harvest"

CSV_COLUMNS = (
    "candidate_text",
    "normalized_text",
    "candidate_type",
    "source",
    "vertical",
    "hit_count",
    "confidence",
    "status",
    "station",
    "company_name",
    "domain",
    "phone",
    "evidence",
    "first_seen",
    "last_seen",
)


# --- helpers ---------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ts_to_iso(ts: float | int | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return ""


def _resolve_db_path(override: str | os.PathLike[str] | None = None) -> Path:
    if override:
        return Path(override)
    try:
        configured = load_settings().db_path
    except Exception:
        configured = "data/pipeline.db"
    return (PROJECT_ROOT / configured) if not Path(configured).is_absolute() else Path(configured)


def load_profile(name: str = DEFAULT_PROFILE, path: Path | None = None) -> dict[str, Any]:
    """Load a harvest profile from YAML. Raises KeyError if missing."""
    profile_path = path or PROFILES_PATH
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    profiles = data.get("profiles") or {}
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none)"
        raise KeyError(f"harvest profile {name!r} not found in {profile_path}; available: {available}")
    return profiles[name]


# --- phrase / signal detection (pure) --------------------------------------


@dataclass
class SignalScan:
    money_problem: list[str] = field(default_factory=list)
    loan_product: list[str] = field(default_factory=list)
    approval_funding: list[str] = field(default_factory=list)
    brand_domain: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    @property
    def has_signal(self) -> bool:
        return bool(self.money_problem or self.loan_product or self.approval_funding)


def normalize_keyword(text: str) -> str:
    """Normalize a keyword for dedup: lowercase, collapse whitespace, strip."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def extract_domain(value: str | None) -> str:
    """Pull a bare domain (no scheme/path) out of a website/url string."""
    if not value:
        return ""
    raw = str(value).strip().lower()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = raw.split("/", 1)[0]
    raw = raw.split("?", 1)[0]
    return raw


def scan_text(text: str, profile: dict[str, Any]) -> SignalScan:
    """Find phrase signals in a block of text (case-insensitive substring)."""
    low = (text or "").lower()

    def hits(key: str) -> list[str]:
        return [p for p in (profile.get(key) or []) if p and p in low]

    return SignalScan(
        money_problem=hits("money_problem_phrases"),
        loan_product=hits("loan_product_phrases"),
        approval_funding=hits("approval_funding_phrases"),
        brand_domain=hits("brand_domain_phrases"),
        rejected=hits("rejected_substrings"),
        ambiguous=hits("ambiguous_review_phrases"),
    )


def classify_status(scan: SignalScan) -> str:
    """Decide candidate status: ready (clear signal) or review (ambiguous)."""
    if scan.has_signal:
        return "ready"
    if scan.ambiguous:
        return "review"
    return "ready"


def signal_candidate_type(scan: SignalScan) -> str:
    """Pick the dominant candidate_type for a phrase-based signal hit."""
    if scan.money_problem:
        return "money_problem"
    if scan.loan_product:
        return "loan_product"
    if scan.approval_funding:
        return "approval_funding"
    return ""


# --- runtime status file ---------------------------------------------------


def read_status() -> dict[str, Any]:
    if not STATUS_FILE.is_file():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_status(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch into the runtime status file (atomic-ish write)."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = read_status()
    state.update(patch)
    state["last_updated"] = _now_iso()
    state.setdefault("host", socket.gethostname())
    tmp = STATUS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATUS_FILE)
    return state


# --- keyword candidate gathering from the DB -------------------------------


@dataclass
class CandidateAccumulator:
    """Accumulates candidates keyed by (normalized_text, candidate_type)."""
    rows: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def add(
        self,
        *,
        candidate_text: str,
        candidate_type: str,
        source: str,
        vertical: str = "",
        station: str = "",
        company_name: str = "",
        domain: str = "",
        phone: str = "",
        evidence: str = "",
        confidence: float = 0.0,
        status: str = "ready",
        hit_ts: float | None = None,
    ) -> None:
        text = (candidate_text or "").strip()
        if not text:
            return
        norm = normalize_keyword(text)
        if not norm:
            return
        key = (norm, candidate_type)
        row = self.rows.get(key)
        ts = float(hit_ts) if hit_ts else None
        if row is None:
            row = {
                "candidate_text": text,
                "normalized_text": norm,
                "candidate_type": candidate_type,
                "source": source,
                "vertical": vertical,
                "hit_count": 1,
                "confidence": confidence,
                "status": status,
                "station": station,
                "company_name": company_name,
                "domain": domain,
                "phone": phone,
                "evidence": evidence,
                "first_seen": ts,
                "last_seen": ts,
            }
            self.rows[key] = row
        else:
            row["hit_count"] += 1
            # keep strongest source/confidence; broaden station/evidence.
            if confidence > row.get("confidence", 0.0):
                row["confidence"] = confidence
            if status == "ready":
                row["status"] = "ready"
            if source and row.get("source") and source != row["source"]:
                row["source"] = f"{row['source']}+{source}" if source not in row["source"] else row["source"]
            elif source and not row.get("source"):
                row["source"] = source
            if company_name and not row.get("company_name"):
                row["company_name"] = company_name
            if domain and not row.get("domain"):
                row["domain"] = domain
            if phone and not row.get("phone"):
                row["phone"] = phone
            if station and station not in (row.get("station") or ""):
                row["station"] = (row.get("station") or "") + ("," if row.get("station") else "") + station
            if evidence and evidence not in (row.get("evidence") or ""):
                base = row.get("evidence") or ""
                row["evidence"] = (base + " | " + evidence) if base else evidence
            for field_name in ("first_seen", "last_seen"):
                cur = row.get(field_name)
                if ts is not None and (cur is None or (field_name == "first_seen" and ts < cur) or (field_name == "last_seen" and ts > cur)):
                    row[field_name] = ts

    def sorted_rows(self) -> list[dict[str, Any]]:
        return sorted(self.rows.values(), key=lambda r: (r.get("confidence", 0.0), r.get("hit_count", 0)), reverse=True)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def gather_keyword_candidates(conn, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect keyword candidates from every available DB source.

    Sources (union, deduped by normalized text + type):
      1. trademark_keyword_candidates  -> brand/domain candidates (CFPB seeds)
      2. detections + transcripts      -> brand/domain + money-problem signals
      3. keyword_hits                  -> money-problem/loan signals (broad net)
    """
    acc = CandidateAccumulator()
    rejected = set(profile.get("rejected_substrings") or [])

    def is_rejected_evidence(text: str) -> bool:
        low = (text or "").lower()
        return any(sub in low for sub in rejected)

    # --- 1. trademark_keyword_candidates (brand/domain seeds) ---------------
    if _table_exists(conn, "trademark_keyword_candidates"):
        rows = conn.execute(
            """
            SELECT keyword, normalized_keyword, variant_type, source_type,
                   status, confidence, score, created_at
            FROM trademark_keyword_candidates
            """
        ).fetchall()
        for r in rows:
            kw = r["keyword"] or ""
            if not kw.strip() or is_rejected_evidence(kw):
                continue
            variant = (r["variant_type"] or "brand").lower()
            ctype = "domain" if variant == "domain" else "brand"
            status = "ready" if (r["status"] in (None, "", "approved_seed", "approved")) else "review"
            score = float(r["score"] or 0.0)
            raw_conf = float(r["confidence"] or 0.0)
            # score is 0-100, confidence is already 0-1 -> normalize to 0-1
            confidence = score / 100.0 if score > 1.5 else raw_conf
            acc.add(
                candidate_text=kw,
                candidate_type=ctype,
                source="trademark_seed",
                confidence=confidence,
                status=status,
                evidence=f"variant={variant}; src={r['source_type']}",
                hit_ts=_parse_created_at(r["created_at"]),
            )

    # --- 2. detections + transcripts (the broad money-problem net) ---------
    if _table_exists(conn, "detections"):
        det_rows = conn.execute(
            """
            SELECT d.id, d.chunk_id, d.ad_category, d.company_name, d.website,
                   d.phone_number, d.offer_summary, d.key_claims, d.confidence,
                   c.station_id, c.start_ts,
                   s.name AS station_name,
                   t.text AS transcript_text
            FROM detections d
            LEFT JOIN chunks c ON c.id = d.chunk_id
            LEFT JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
            """
        ).fetchall()
        for r in det_rows:
            company = (r["company_name"] or "").strip()
            website = (r["website"] or "").strip()
            domain = extract_domain(website) if website else ""
            offer = r["offer_summary"] or ""
            claims = r["key_claims"] or ""
            transcript = r["transcript_text"] or ""
            evidence_blob = " ".join(part for part in [company, website, offer, claims, transcript] if part)
            scan = scan_text(evidence_blob, profile)
            station = r["station_name"] or ""
            hit_ts = r["start_ts"]
            base_conf = float(r["confidence"] or 0.0)
            rejected_blob = is_rejected_evidence(evidence_blob)

            # GATE: drop rejected verticals (tax/insurance/timeshare/real-estate/...)
            # that carry no money-problem/loan signal. Also drop neutral products
            # (wine, mattresses, antivirus, B2B marketing) that have neither a
            # money signal nor ambiguous debt language.
            if rejected_blob and not scan.has_signal:
                continue
            if not scan.has_signal and not scan.ambiguous:
                continue

            status = "ready" if scan.has_signal else "review"
            brand_conf = max(base_conf, 0.7) if scan.has_signal else 0.4

            # brand candidate from company name
            if company and not is_rejected_evidence(company):
                acc.add(
                    candidate_text=company,
                    candidate_type="brand",
                    source="detection",
                    vertical=r["ad_category"] or "",
                    station=station,
                    company_name=company,
                    domain=domain,
                    phone=(r["phone_number"] or ""),
                    evidence=_excerpt(offer or transcript),
                    confidence=brand_conf,
                    status=status,
                    hit_ts=hit_ts,
                )
            # domain candidate
            if domain and not is_rejected_evidence(domain):
                acc.add(
                    candidate_text=domain,
                    candidate_type="domain",
                    source="detection",
                    vertical=r["ad_category"] or "",
                    station=station,
                    company_name=company,
                    domain=domain,
                    evidence=_excerpt(transcript or offer),
                    confidence=brand_conf,
                    status=status,
                    hit_ts=hit_ts,
                )

            # phrase-based signal candidates (money_problem / loan_product / approval_funding)
            for phrase in _unique(scan.money_problem + scan.loan_product + scan.approval_funding):
                ptype = (
                    "money_problem" if phrase in scan.money_problem
                    else "loan_product" if phrase in scan.loan_product
                    else "approval_funding"
                )
                acc.add(
                    candidate_text=phrase,
                    candidate_type=ptype,
                    source="detection",
                    vertical=r["ad_category"] or "",
                    station=station,
                    company_name=company,
                    domain=domain,
                    phone=(r["phone_number"] or ""),
                    evidence=_excerpt(transcript or offer or evidence_blob),
                    confidence=max(base_conf, 0.75),
                    status="ready",
                    hit_ts=hit_ts,
                )

            # ambiguous debt/bills/credit (no clear signal) -> save phrases for review
            if not scan.has_signal and scan.ambiguous:
                for phrase in _unique(scan.ambiguous):
                    acc.add(
                        candidate_text=phrase,
                        candidate_type="money_problem",
                        source="detection",
                        vertical=r["ad_category"] or "",
                        station=station,
                        evidence=_excerpt(transcript or offer),
                        confidence=0.4,
                        status="review",
                        hit_ts=hit_ts,
                    )

    # --- 3. keyword_hits (broad net over stored hits) ----------------------
    if _table_exists(conn, "keyword_hits"):
        kw_rows = conn.execute(
            """
            SELECT kh.keyword, kh.context_excerpt, kh.hit_ts,
                   s.name AS station_name
            FROM keyword_hits kh
            LEFT JOIN chunks c ON c.id = kh.chunk_id
            LEFT JOIN stations s ON s.id = c.station_id
            """
        ).fetchall()
        for r in kw_rows:
            kw = (r["keyword"] or "").strip()
            if not kw:
                continue
            ctx = r["context_excerpt"] or ""
            blob = f"{kw} {ctx}"
            scan = scan_text(blob, profile)
            if is_rejected_evidence(blob) and not scan.has_signal:
                continue  # drop rejected-vertical legacy hits
            if scan.has_signal:
                ptype = signal_candidate_type(scan)
                status = "ready"
                conf = 0.7
            elif scan.ambiguous:
                ptype = "money_problem"
                status = "review"
                conf = 0.35
            else:
                continue
            acc.add(
                candidate_text=kw,
                candidate_type=ptype,
                source="keyword_hit",
                station=r["station_name"] or "",
                evidence=_excerpt(ctx or kw),
                confidence=conf,
                status=status,
                hit_ts=r["hit_ts"],
            )

    return acc.sorted_rows()


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _excerpt(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def _parse_created_at(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # ISO string (created_at in trademark_keyword_candidates is TEXT)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# --- export + summary writers ----------------------------------------------


def _row_for_output(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_text": row.get("candidate_text", ""),
        "normalized_text": row.get("normalized_text", ""),
        "candidate_type": row.get("candidate_type", ""),
        "source": row.get("source", ""),
        "vertical": row.get("vertical", ""),
        "hit_count": row.get("hit_count", 0),
        "confidence": round(float(row.get("confidence") or 0.0), 4),
        "status": row.get("status", "ready"),
        "station": row.get("station", ""),
        "company_name": row.get("company_name", ""),
        "domain": row.get("domain", ""),
        "phone": row.get("phone", ""),
        "evidence": row.get("evidence", ""),
        "first_seen": _ts_to_iso(row.get("first_seen")),
        "last_seen": _ts_to_iso(row.get("last_seen")),
    }


def export_candidates(
    rows: list[dict[str, Any]],
    out_dir: Path | None = None,
    limit: int | None = None,
) -> dict[str, Path]:
    """Write CSV + JSONL candidate files. Returns {csv, jsonl} paths."""
    target = out_dir or EXPORTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    selected = rows if limit is None else rows[:limit]
    out_rows = [_row_for_output(r) for r in selected]

    csv_path = target / "overnight_keyword_candidates.csv"
    jsonl_path = target / "overnight_keyword_candidates.jsonl"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for r in out_rows:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {"csv": csv_path, "jsonl": jsonl_path, "rows": len(out_rows)}


def write_summary(
    rows: list[dict[str, Any]],
    status: dict[str, Any],
    out_path: Path | None = None,
) -> Path:
    """Write exports/overnight_keyword_summary.md."""
    target = out_path or (EXPORTS_DIR / "overnight_keyword_summary.md")
    target.parent.mkdir(parents=True, exist_ok=True)

    by_type: dict[str, int] = defaultdict(int)
    by_status: dict[str, int] = defaultdict(int)
    for r in rows:
        by_type[r.get("candidate_type", "")] += 1
        by_status[r.get("status", "ready")] += 1

    lines: list[str] = []
    lines.append("# Overnight Keyword Harvest Summary")
    lines.append("")
    lines.append(f"Generated: {_now_iso()}")
    lines.append("")
    state = status.get("state", "idle")
    lines.append("## Session")
    lines.append(f"- state: {state}")
    if status.get("profile"):
        lines.append(f"- profile: {status.get('profile')}")
    if status.get("started_at"):
        lines.append(f"- started_at: {status.get('started_at')}")
    if status.get("stopped_at"):
        lines.append(f"- stopped_at: {status.get('stopped_at')}")
    probe = status.get("probe") or {}
    if probe:
        lines.append(f"- last probe: {probe.get('ok', 0)}/{probe.get('tested', 0)} streams reachable")
    lines.append("")
    lines.append("## Candidates")
    lines.append(f"- total: {len(rows)}")
    for ctype in ("brand", "domain", "money_problem", "loan_product", "approval_funding"):
        if by_type.get(ctype):
            lines.append(f"- {ctype}: {by_type[ctype]}")
    for st in ("ready", "review"):
        if by_status.get(st):
            lines.append(f"- status {st}: {by_status[st]}")
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    lines.append("| # | candidate | type | hits | conf | status | station |")
    lines.append("|---|-----------|------|------|------|--------|---------|")
    for i, r in enumerate(rows[:25], 1):
        station = (r.get("station") or "").split(",")[0]
        lines.append(
            f"| {i} | {r.get('candidate_text','')} | {r.get('candidate_type','')} | "
            f"{r.get('hit_count',0)} | {round(float(r.get('confidence') or 0),2)} | "
            f"{r.get('status','ready')} | {station} |"
        )
    lines.append("")
    lines.append("_Ready_ candidates are high-confidence (clear money-problem/loan/brand signal).")
    lines.append("_Review_ candidates use ambiguous debt/bills/credit language and need a human look.")
    lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")
    return target


# --- stream probe ----------------------------------------------------------


def build_probe_command(url: str, duration_seconds: int) -> list[str]:
    """ffmpeg command that captures `duration_seconds` to /dev/null (liveness)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-i",
        url,
        "-t",
        str(duration_seconds),
        "-f",
        "null",
        "-",
    ]


def probe_stream(url: str, duration_seconds: int, timeout_seconds: int) -> dict[str, Any]:
    """Probe one stream URL. Returns {ok, duration, error}."""
    tested_at = _now_iso()
    cmd = build_probe_command(url, duration_seconds)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        ok = proc.returncode == 0
        err = (proc.stderr or "").strip()
        return {
            "ok": ok,
            "duration_tested_seconds": duration_seconds if ok else 0,
            "error": (err[:300] if err else ""),
            "tested_at": tested_at,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "duration_tested_seconds": 0, "error": f"timeout after {timeout_seconds}s", "tested_at": tested_at}
    except FileNotFoundError:
        return {"ok": False, "duration_tested_seconds": 0, "error": "ffmpeg not found on PATH", "tested_at": tested_at}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "duration_tested_seconds": 0, "error": f"{type(exc).__name__}: {exc}", "tested_at": tested_at}


def probe_stations(limit: int = 20, profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Probe up to `limit` enabled stations (falls back to all configured)."""
    profile = profile or {}
    try:
        stations = load_stations()
    except Exception:
        return []
    enabled = [s for s in stations if s.enabled]
    pool = enabled if enabled else stations
    selected = pool[:limit]
    duration = int(profile.get("probe_duration_seconds", 6))
    timeout = int(profile.get("probe_timeout_seconds", 20))
    results: list[dict[str, Any]] = []
    for st in selected:
        probe = probe_stream(st.url, duration, timeout)
        results.append(
            {
                "station": st.name,
                "display_name": st.display_name or st.name,
                "url": st.url,
                "format": st.format,
                **probe,
            }
        )
    return results


# --- DB status snapshot ----------------------------------------------------


def db_snapshot(db_path: Path) -> dict[str, Any]:
    """Read-only harvest counts from the pipeline DB (safe during ingest)."""
    snap: dict[str, Any] = {"db_path": str(db_path), "exists": db_path.is_file()}
    if not db_path.is_file():
        return snap
    conn = get_connection(db_path, read_only=True)
    try:
        def count(table: str, where: str = "") -> int:
            if not _table_exists(conn, table):
                return 0
            return int(conn.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0])

        snap.update(
            {
                "chunks": count("chunks"),
                "chunks_done": count("chunks", "WHERE status='done'"),
                "chunks_pending": count("chunks", "WHERE status='pending'"),
                "transcripts": count("transcripts"),
                "detections": count("detections"),
                "keyword_hits": count("keyword_hits"),
                "trademark_keyword_candidates": count("trademark_keyword_candidates"),
                "advertiser_entities": count("advertiser_entities"),
                "stations_enabled": count("stations", "WHERE enabled=1"),
            }
        )
    finally:
        conn.close()
    return snap


# --- CLI command handlers --------------------------------------------------


def _print_probe_table(results: list[dict[str, Any]]) -> None:
    print(f"\nProbed {len(results)} station(s):\n")
    print(f"{'STATION':<22} {'OK':<4} {'SECS':<5} URL")
    print("-" * 80)
    for r in results:
        ok = "yes" if r.get("ok") else "NO"
        print(f"{r['station']:<22} {ok:<4} {r.get('duration_tested_seconds',0):<5} {r['url']}")
        if r.get("error"):
            print(f"{'':22} -> {r['error']}")
    ok_n = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok_n}/{len(results)} reachable.")


def cmd_probe(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    results = probe_stations(limit=args.limit, profile=profile)
    _print_probe_table(results)
    ok_n = sum(1 for r in results if r.get("ok"))
    write_status(
        {
            "last_command": "probe",
            "profile": args.profile,
            "probe": {"tested": len(results), "ok": ok_n, "at": _now_iso(), "results": results},
        }
    )
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)  # validates the profile exists
    # probe the profile's stations so the operator sees reachability immediately
    results = probe_stations(limit=int(profile.get("max_stations", 20)), profile=profile)
    ok_n = sum(1 for r in results if r.get("ok"))
    state = write_status(
        {
            "last_command": "start",
            "state": "running",
            "profile": args.profile,
            "pid": os.getpid(),
            "started_at": _now_iso(),
            "stopped_at": None,
            "probe": {"tested": len(results), "ok": ok_n, "at": _now_iso(), "results": results},
            "note": "Audio ingest runs via docker compose; this control marks the harvest session and probes streams.",
        }
    )
    _print_probe_table(results)
    print(f"\nHarvest session STARTED (profile={args.profile}, pid={state['pid']}).")
    print("Keep the ingest stack (ingestor+worker+alerter) running via docker compose.")
    print("Run `python scripts/harvest_control.py export` to pull keyword candidates.")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    prev = read_status()
    started = prev.get("started_at")
    duration = ""
    if started:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            duration = f" (ran {(datetime.now(tz=timezone.utc) - start_dt)})"
        except ValueError:
            duration = ""
    write_status({"last_command": "stop", "state": "stopped", "stopped_at": _now_iso(), "pid": None})
    print(f"Harvest session STOPPED{duration}.")
    print("Tip: run `python scripts/harvest_control.py export` then `summary` to finalize keywords.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    status = read_status()
    snap = db_snapshot(_resolve_db_path(args.db))
    print("=== Harvest runtime status ===")
    if not status:
        print("  (no session recorded — run `start` or `probe`)")
    else:
        for key in ("state", "profile", "pid", "started_at", "stopped_at", "last_updated"):
            if status.get(key) is not None:
                print(f"  {key}: {status.get(key)}")
        probe = status.get("probe") or {}
        if probe:
            print(f"  last probe: {probe.get('ok',0)}/{probe.get('tested',0)} reachable @ {probe.get('at','')}")
        exp = status.get("export") or {}
        if exp:
            print(f"  last export: {exp.get('rows',0)} rows @ {exp.get('at','')} -> {exp.get('csv','')}")
    print("\n=== Pipeline DB snapshot ===")
    for key, value in snap.items():
        print(f"  {key}: {value}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    db_path = _resolve_db_path(args.db)
    if not db_path.is_file():
        print(f"No pipeline DB at {db_path}. Nothing to export.")
        return 1
    conn = get_connection(db_path, read_only=True)
    try:
        rows = gather_keyword_candidates(conn, profile)
    finally:
        conn.close()
    paths = export_candidates(rows, limit=args.limit)
    write_summary(rows, read_status())
    write_status(
        {
            "last_command": "export",
            "profile": args.profile,
            "export": {"rows": paths["rows"], "csv": str(paths["csv"]), "jsonl": str(paths["jsonl"]), "at": _now_iso()},
        }
    )
    print(f"Exported {paths['rows']} keyword candidates:")
    print(f"  CSV  : {paths['csv']}")
    print(f"  JSONL: {paths['jsonl']}")
    print(f"  MD   : {EXPORTS_DIR / 'overnight_keyword_summary.md'}")
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    db_path = _resolve_db_path(args.db)
    conn = get_connection(db_path, read_only=True)
    try:
        rows = gather_keyword_candidates(conn, profile)
    finally:
        conn.close()
    selected = rows[: args.limit]
    print(f"\nTop {len(selected)} keyword candidate(s):\n")
    print(f"{'#':>3}  {'CANDIDATE':<34} {'TYPE':<16} {'HITS':>4} {'CONF':>5} {'STATUS':<7} {'STATION'}")
    print("-" * 100)
    for i, r in enumerate(selected, 1):
        station = (r.get("station") or "").split(",")[0]
        print(
            f"{i:>3}  {(r.get('candidate_text') or ''):<34} {r.get('candidate_type',''):<16} "
            f"{r.get('hit_count',0):>4} {round(float(r.get('confidence') or 0),2):>5} "
            f"{r.get('status','ready'):<7} {station}"
        )
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    db_path = _resolve_db_path(args.db)
    conn = get_connection(db_path, read_only=True)
    try:
        rows = gather_keyword_candidates(conn, profile)
    finally:
        conn.close()
    path = write_summary(rows, read_status())
    print(f"Wrote summary: {path}")
    print(f"  total candidates: {len(rows)}")
    return 0


# --- argparse --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harvest_control",
        description="Radio Ad Pipeline harvest control (Safe Run Mode).",
    )
    parser.add_argument("--db", default=None, help="Override pipeline DB path (default: settings.yaml db_path)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_profile(p: argparse.ArgumentParser) -> None:
        p.add_argument("--profile", default=DEFAULT_PROFILE, help=f"Harvest profile (default: {DEFAULT_PROFILE})")

    p_probe = sub.add_parser("probe", help="Probe station streams for reachability")
    p_probe.add_argument("--limit", type=int, default=20, help="Max stations to probe (default 20)")
    add_profile(p_probe)

    p_start = sub.add_parser("start", help="Start a harvest session")
    p_start.add_argument("--limit", type=int, default=None, help="Override max stations to probe")
    add_profile(p_start)

    sub.add_parser("stop", help="Stop the running harvest session")
    sub.add_parser("status", help="Show runtime + DB status")

    p_export = sub.add_parser("export", help="Export keyword candidates to CSV/JSONL")
    p_export.add_argument("--limit", type=int, default=None, help="Max candidates to export (default: all)")
    add_profile(p_export)

    p_top = sub.add_parser("top", help="Print top keyword candidates")
    p_top.add_argument("--limit", type=int, default=50, help="Number to show (default 50)")
    add_profile(p_top)

    p_summary = sub.add_parser("summary", help="Write exports/overnight_keyword_summary.md")
    add_profile(p_summary)
    return parser


_HANDLERS = {
    "probe": cmd_probe,
    "start": cmd_start,
    "stop": cmd_stop,
    "status": cmd_status,
    "export": cmd_export,
    "top": cmd_top,
    "summary": cmd_summary,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = _HANDLERS[args.command]
    try:
        return handler(args)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
