"""Safe harvest-control API layer for the dashboard.

This wraps the existing ``scripts/harvest_control.py`` CLI behind a *fixed*
command allowlist. No user input ever becomes a shell argument — each action
maps to a constant argv tuple executed via ``subprocess.run`` (no shell).

Read-only data helpers (status file, DB snapshot, detections, queue health,
station config) use ``read_only=True`` connections so they stay compatible
with the dashboard's read-only guarantee.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from dashboard import queries
from shared.config import load_stations
from shared.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
STATUS_FILE = RUNTIME_DIR / "harvest_status.json"
LOGS_DIR = PROJECT_ROOT / "logs"

DEFAULT_PROFILE = "overnight_keyword_harvest"
PROBE_LIMIT = 20
SUBPROCESS_TIMEOUT = 300  # probe of up to 20 stations x ~6-20s each

# ---------------------------------------------------------------------------
# Fixed command allowlist — the ONLY commands this module will ever spawn.
# Each value is a complete argv tuple; nothing from a request is interpolated.
# ---------------------------------------------------------------------------
ALLOWED_COMMANDS: dict[str, tuple[str, ...]] = {
    "probe": (sys.executable, "scripts/harvest_control.py", "probe", "--limit", str(PROBE_LIMIT)),
    "start": (
        sys.executable,
        "scripts/harvest_control.py",
        "start",
        "--profile",
        DEFAULT_PROFILE,
    ),
    "stop": (
        sys.executable,
        "scripts/harvest_control.py",
        "stop",
        "--profile",
        DEFAULT_PROFILE,
    ),
    "status": (sys.executable, "scripts/harvest_control.py", "status"),
}


class UnknownActionError(ValueError):
    """Raised when an action is not in the allowlist."""


class HarvestAlreadyRunningError(RuntimeError):
    """Raised when a start is requested while a session is already running."""


def allowed_actions() -> list[str]:
    """Return the sorted list of actions this module may execute."""
    return sorted(ALLOWED_COMMANDS)


# ---------------------------------------------------------------------------
# Subprocess execution — single monkeypatchable seam for tests.
# ---------------------------------------------------------------------------
def _run_subprocess(argv: tuple[str, ...]) -> dict[str, Any]:
    """Run a fixed argv (no shell) and return a structured result.

    Tests monkeypatch this function to avoid shelling out to ffmpeg / the real
    CLI. Production code spawns the real process.
    """
    completed = subprocess.run(
        list(argv),
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def is_running() -> bool:
    """True if the runtime status file says a harvest session is running."""
    status = read_status_file()
    return bool(status.get("state") == "running")


def run_control_action(action: str) -> dict[str, Any]:
    """Execute a fixed harvest-control action safely.

    Validates ``action`` against the allowlist, guards ``start`` against a
    session that is already running, then spawns the CLI via ``_run_subprocess``.
    Returns the subprocess result merged with the post-action status snapshot.
    Raises ``UnknownActionError`` for unknown actions and
    ``HarvestAlreadyRunningError`` when starting twice.
    """
    if action not in ALLOWED_COMMANDS:
        raise UnknownActionError(action)
    if action == "start" and is_running():
        raise HarvestAlreadyRunningError(
            "A harvest session is already running. Stop it before starting again."
        )
    argv = ALLOWED_COMMANDS[action]
    result = _run_subprocess(argv)
    result["action"] = action
    result["status"] = read_status_file()
    return result


# ---------------------------------------------------------------------------
# Runtime status file (runtime/harvest_status.json) — written by the CLI.
# ---------------------------------------------------------------------------
def read_status_file() -> dict[str, Any]:
    if not STATUS_FILE.is_file():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# Read-only DB helpers
# ---------------------------------------------------------------------------
def _market_map() -> dict[str, str]:
    """Map station name -> market from stations.yaml (pool.market)."""
    out: dict[str, str] = {}
    try:
        for st in load_stations():
            if st.pool and st.pool.market:
                out[st.name] = st.pool.market
    except Exception:
        pass
    return out


def harvest_db_snapshot(db_path: Path) -> dict[str, Any]:
    """Read-only harvest counts used by the status view.

    Mirrors the data surfaced by ``harvest_control.py status`` but read
    directly from the dashboard's DB handle (read-only, safe during ingest).
    """
    snap: dict[str, Any] = {"exists": db_path.is_file()}
    if not db_path.is_file():
        return snap
    conn = get_connection(db_path, read_only=True)
    try:
        def count(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0])
            except Exception:
                return 0

        snap["chunks_created"] = count("SELECT COUNT(*) FROM chunks")
        snap["chunks_processed"] = count("SELECT COUNT(*) FROM chunks WHERE status='done'")
        snap["chunks_dropped"] = count("SELECT COUNT(*) FROM chunks WHERE status='dropped'")
        snap["pending_queue"] = count("SELECT COUNT(*) FROM chunks WHERE status='pending'")
        snap["detections_total"] = count("SELECT COUNT(*) FROM detections")
        snap["loan_keyword_hits"] = count("SELECT COUNT(*) FROM keyword_hits")
        snap["unique_advertisers"] = count(
            "SELECT COUNT(DISTINCT company_name) FROM detections "
            "WHERE company_name IS NOT NULL AND company_name != ''"
        )
    finally:
        conn.close()
    return snap


def fetch_harvest_status(db_path: Path) -> dict[str, Any]:
    """Combined status: runtime session file + live DB snapshot."""
    status = read_status_file()
    snap = harvest_db_snapshot(db_path)
    probe = status.get("probe") or {}
    return {
        "profile": status.get("profile"),
        "running": is_running(),
        "state": status.get("state"),
        "started_at": status.get("started_at"),
        "stopped_at": status.get("stopped_at"),
        "last_updated": status.get("last_updated"),
        "last_command": status.get("last_command"),
        "note": status.get("note"),
        "active_stations": probe.get("ok", 0),
        "tested_stations": probe.get("tested", 0),
        "last_probe_at": probe.get("at"),
        "probe_results": probe.get("results") or [],
        "export": status.get("export") or {},
        "db_path": str(db_path),
        **snap,
    }


def harvest_warning(status: dict[str, Any]) -> str | None:
    """Return a human-readable warning if the dashboard's DB looks empty or stale.

    Used to surface a clear banner on /radio-harvest so the operator never
    silently acts against the wrong (empty/host) DB. Returns None when healthy.
    """
    if not status.get("exists", True):
        return (
            "No pipeline database found at the configured path. The dashboard is "
            "reading a non-existent DB — status numbers will all be zero."
        )
    chunks = int(status.get("chunks_created", 0) or 0)
    detections = int(status.get("detections_total", 0) or 0)
    if chunks == 0:
        return (
            "The dashboard's DB has 0 chunks. This is either a fresh install or the "
            "wrong (empty) DB. Confirm the ingestor is writing to the same DB."
        )
    if detections == 0 and chunks > 0:
        return (
            "Chunks exist but 0 detections have been recorded. The worker may not "
            "be processing, or this is a stale copy of the DB."
        )
    return None


def fetch_per_station(db_path: Path) -> list[dict[str, Any]]:
    """Per-station queue health (pending/dropped/done) for enabled stations."""
    enabled_names = {s.name for s in load_stations() if s.enabled}
    market = _market_map()
    conn = get_connection(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT s.name AS station_name, s.display_name AS display_name,
                   SUM(CASE WHEN c.status='pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN c.status='dropped' THEN 1 ELSE 0 END) AS dropped,
                   SUM(CASE WHEN c.status='done' THEN 1 ELSE 0 END) AS done,
                   COUNT(c.id) AS total
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            GROUP BY s.id, s.name, s.display_name
            ORDER BY s.name
            """
        ).fetchall()
    finally:
        conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        name = row["station_name"]
        if enabled_names and name not in enabled_names:
            continue
        out.append(
            {
                "station": name,
                "display_name": row["display_name"] or name,
                "market": market.get(name, ""),
                "pending": int(row["pending"] or 0),
                "dropped": int(row["dropped"] or 0),
                "done": int(row["done"] or 0),
                "total": int(row["total"] or 0),
            }
        )
    return out


def fetch_harvest_detections(db_path: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    """Recent ad detections with station, advertiser, transcript snippet."""
    market = _market_map()
    conn = get_connection(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT d.id AS detection_id, d.company_name, d.ad_category,
                   d.offer_summary, d.confidence,
                   c.start_ts, c.path AS chunk_path, c.status AS chunk_status,
                   s.name AS station_name, s.display_name AS station_display,
                   t.text AS transcript_text,
                   kh.keywords
            FROM detections d
            LEFT JOIN chunks c ON c.id = d.chunk_id
            LEFT JOIN stations s ON s.id = c.station_id
            LEFT JOIN transcripts t ON t.chunk_id = c.id
            LEFT JOIN (
                SELECT detection_id, GROUP_CONCAT(keyword, ', ') AS keywords
                FROM keyword_hits
                WHERE detection_id IS NOT NULL
                GROUP BY detection_id
            ) kh ON kh.detection_id = d.id
            WHERE d.is_ad = 1
            ORDER BY d.id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    results: list[dict[str, Any]] = []
    for row in rows:
        station_name = row["station_name"]
        snippet = (row["transcript_text"] or "").strip()
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        results.append(
            {
                "detection_id": row["detection_id"],
                "start_ts": row["start_ts"],
                "station": station_name,
                "station_display": row["station_display"] or station_name,
                "market": market.get(station_name, "") if station_name else "",
                "company_name": row["company_name"],
                "ad_category": row["ad_category"],
                "offer_summary": row["offer_summary"],
                "keywords": row["keywords"],
                "confidence": row["confidence"],
                "transcript_snippet": snippet,
                "chunk_path": row["chunk_path"],
                "chunk_status": row["chunk_status"],
            }
        )
    return results


def fetch_queue_health_detail(db_path: Path) -> dict[str, Any]:
    """Queue health: reuse dashboard query + per-station + oldest-pending age."""
    base = queries.fetch_queue_health(db_path)
    oldest_age: float | None = None
    conn = get_connection(db_path, read_only=True)
    try:
        try:
            row = conn.execute(
                "SELECT MIN(start_ts) AS oldest FROM chunks WHERE status='pending'"
            ).fetchone()
            oldest = row["oldest"]
            if oldest is not None:
                oldest_age = max(0.0, time.time() - float(oldest))
        except Exception:
            oldest_age = None
    finally:
        conn.close()
    return {
        **base,
        "per_station": fetch_per_station(db_path),
        "oldest_pending_age_seconds": oldest_age,
        # Processing latency is not tracked in the DB; surface honestly as None.
        "average_processing_delay_seconds": None,
        "log_error_counts": _count_log_errors(),
    }


def fetch_station_config() -> list[dict[str, Any]]:
    """Station config from config/stations.yaml (operator reference view)."""
    out: list[dict[str, Any]] = []
    try:
        stations = load_stations()
    except Exception:
        return out
    for st in stations:
        out.append(
            {
                "station_id": st.name,
                "display_name": st.display_name or st.name,
                "market": (st.pool.market if st.pool else None),
                "state": (st.pool.vertical if st.pool else None),
                "stream_url": st.url,
                "format": st.format,
                "enabled": st.enabled,
            }
        )
    return out


def _count_log_errors() -> dict[str, int]:
    """Best-effort ERROR-line counts from the latest worker log."""
    counts: dict[str, int] = {"ffmpeg": 0, "asr": 0, "db": 0}
    try:
        if not LOGS_DIR.is_dir():
            return counts
        candidates = sorted(
            (p for p in LOGS_DIR.glob("*.log")), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not candidates:
            return counts
        text = candidates[0].read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if "ERROR" not in line:
                continue
            low = line.lower()
            if "ffmpeg" in low:
                counts["ffmpeg"] += 1
            if "asr" in low or "whisper" in low or "transcrib" in low:
                counts["asr"] += 1
            if "sqlite" in low or "database" in low or "db " in low or "integrity" in low:
                counts["db"] += 1
    except Exception:
        pass
    return counts


__all__ = [
    "ALLOWED_COMMANDS",
    "DEFAULT_PROFILE",
    "HarvestAlreadyRunningError",
    "UnknownActionError",
    "allowed_actions",
    "fetch_harvest_detections",
    "fetch_harvest_status",
    "fetch_per_station",
    "fetch_queue_health_detail",
    "fetch_station_config",
    "harvest_db_snapshot",
    "harvest_warning",
    "is_running",
    "read_status_file",
    "run_control_action",
]
