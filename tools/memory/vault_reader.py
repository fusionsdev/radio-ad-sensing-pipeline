"""Read-only parsers for project-memory vault and harness reports."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.harness.lib.common import REPORTS_DIR
from tools.memory._common import DECISIONS_DIR, INCIDENTS_DIR, MEMORY_ROOT, RUNBOOKS_DIR, STATIONS_DIR
from tools.memory.analytics import (
    aggregate_categories,
    classify_decision,
    classify_incident,
    count_harness_report_files,
    count_station_history_entries,
    count_vault_growth,
    is_milestone,
)
from tools.memory.memory_report import FRESHNESS_DAYS, LATEST_STATUS, build_memory_health
from tools.memory.metrics_report import LATEST_JSON, generate_report

DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
HISTORY_LINE_RE = re.compile(
    r"^\-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s+—\s+(\w+):\s*(.*)$",
    re.MULTILINE,
)


def _status_label(value: str) -> str:
    mapping = {"pass": "PASS", "warning": "WARNING", "fail": "FAIL"}
    return mapping.get(value.lower(), value.upper())


def _section_text(text: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title.lower().startswith("decision:"):
                return title.split(":", 1)[-1].strip()
            if title.lower().startswith("incident"):
                return title
            return title
    return fallback


def _date_from_filename(path: Path) -> str:
    match = DATE_PREFIX_RE.match(path.stem)
    if match:
        return match.group(1)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return mtime.strftime("%Y-%m-%d")


def _sort_mtime(paths: list[Path], reverse: bool = True) -> list[Path]:
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=reverse)


def fetch_memory_health() -> dict[str, Any]:
    if not MEMORY_ROOT.exists():
        return {
            "status": "FAIL",
            "core_files": "FAIL",
            "runbooks": "FAIL",
            "stations": "FAIL",
            "decisions": "FAIL",
            "freshness": "FAIL",
            "links": "FAIL",
            "degraded": True,
            "detail": "project-memory/ not found",
        }
    health = build_memory_health()
    sub = health["subchecks"]
    overall = "PASS" if health["status"] == "pass" else "FAIL"
    if sub.get("freshness") == "warning" and overall == "PASS":
        overall = "WARNING"
    return {
        "status": overall,
        "core_files": _status_label(sub.get("core_files", "fail")),
        "runbooks": _status_label(sub.get("runbooks", "fail")),
        "stations": _status_label(sub.get("stations", "fail")),
        "decisions": _status_label(sub.get("decisions", "fail")),
        "freshness": _status_label(sub.get("freshness", "fail")),
        "links": _status_label(sub.get("links", "fail")),
        "degraded": False,
        "vault_markdown_count": health.get("vault_markdown_count", 0),
    }


def fetch_memory_status() -> dict[str, Any]:
    health = fetch_memory_health()
    freshness = build_memory_health()["freshness"] if MEMORY_ROOT.exists() else {
        "age_days": None,
        "detail": "project-memory/ not found",
        "status": "fail",
    }
    latest_excerpt = ""
    if LATEST_STATUS.exists():
        lines = LATEST_STATUS.read_text(encoding="utf-8").splitlines()
        latest_excerpt = "\n".join(lines[:12])

    return {
        **health,
        "latest_status_path": str(LATEST_STATUS.relative_to(MEMORY_ROOT.parent))
        if LATEST_STATUS.exists()
        else None,
        "latest_status_age_days": freshness.get("age_days"),
        "latest_status_fresh": freshness.get("status") == "pass",
        "freshness_threshold_days": FRESHNESS_DAYS,
        "latest_status_excerpt": latest_excerpt or None,
    }


def fetch_harness_latest() -> dict[str, Any]:
    json_path = REPORTS_DIR / "latest.json"
    md_path = REPORTS_DIR / "latest.md"
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data["source"] = "json"
            return data
        except json.JSONDecodeError:
            pass
    if md_path.exists():
        return {
            "source": "md",
            "status": "unknown",
            "overnight_readiness": "unknown",
            "timestamp": None,
            "markdown": md_path.read_text(encoding="utf-8"),
            "degraded": True,
        }
    return {
        "source": "none",
        "status": "unknown",
        "overnight_readiness": "unknown",
        "timestamp": None,
        "degraded": True,
        "detail": "harness report not found",
    }


def fetch_decisions(limit: int = 10) -> list[dict[str, Any]]:
    if not DECISIONS_DIR.exists():
        return []
    paths = _sort_mtime(list(DECISIONS_DIR.glob("*.md")))[:limit]
    rows: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        title = _title_from_markdown(text, path.stem.replace("-", " "))
        context = _section_text(text, "Context")
        decision = _section_text(text, "Decision")
        summary = (decision or context or "").split("\n")[0][:240]
        rows.append(
            {
                "date": _date_from_filename(path),
                "title": title,
                "summary": summary or "(no summary)",
                "path": str(path.relative_to(MEMORY_ROOT.parent)),
            }
        )
    return rows


def fetch_incidents(limit: int = 10) -> list[dict[str, Any]]:
    if not INCIDENTS_DIR.exists():
        return []
    paths = _sort_mtime(list(INCIDENTS_DIR.glob("*.md")))[:limit]
    rows: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        title = _title_from_markdown(text, path.stem.replace("-", " "))
        symptoms = _section_text(text, "Symptoms")
        first_symptom = symptoms.split("\n")[0][:240] if symptoms else "(no symptoms recorded)"
        rows.append(
            {
                "date": _date_from_filename(path),
                "title": title,
                "symptoms": first_symptom,
                "path": str(path.relative_to(MEMORY_ROOT.parent)),
            }
        )
    return rows


def fetch_station_memories(limit: int = 20) -> list[dict[str, Any]]:
    if not STATIONS_DIR.exists():
        return []
    paths = [
        p
        for p in STATIONS_DIR.glob("*.md")
        if p.name.lower() not in {"batch policy.md"}
    ]
    paths = _sort_mtime(paths)[:limit]
    rows: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        station = path.stem.upper()
        status_raw = _section_text(text, "Status").split("\n")[0].strip().lower() or "unknown"
        history = _section_text(text, "History")
        last_change = ""
        matches = HISTORY_LINE_RE.findall(history)
        if matches:
            last_change = f"{matches[-1][0]} — {matches[-1][1]}"
        rows.append(
            {
                "station": station,
                "status": status_raw.replace(" ", "_"),
                "last_change": last_change or "—",
                "path": str(path.relative_to(MEMORY_ROOT.parent)),
            }
        )
    return rows


def _all_decision_paths() -> list[Path]:
    if not DECISIONS_DIR.exists():
        return []
    return list(DECISIONS_DIR.glob("*.md"))


def _all_incident_paths() -> list[Path]:
    if not INCIDENTS_DIR.exists():
        return []
    return list(INCIDENTS_DIR.glob("*.md"))


def fetch_memory_metrics() -> dict[str, Any]:
    if not MEMORY_ROOT.exists():
        return {
            "total_decisions": 0,
            "total_incidents": 0,
            "total_station_changes": 0,
            "total_runbooks": 0,
            "total_harness_runs": 0,
            "memory_growth_7d": 0,
            "vault_markdown_total": 0,
            "degraded": True,
        }
    runbooks = len(list(RUNBOOKS_DIR.glob("*.md"))) if RUNBOOKS_DIR.exists() else 0
    return {
        "total_decisions": len(_all_decision_paths()),
        "total_incidents": len(_all_incident_paths()),
        "total_station_changes": count_station_history_entries(),
        "total_runbooks": runbooks,
        "total_harness_runs": max(count_harness_report_files(), 1 if (REPORTS_DIR / "latest.json").exists() else 0),
        "memory_growth_7d": count_vault_growth(7),
        "vault_markdown_total": len(
            [p for p in MEMORY_ROOT.rglob("*.md") if ".obsidian" not in p.parts and ".smart-env" not in p.parts]
        ),
        "degraded": False,
    }


def fetch_memory_timeline(limit: int = 50) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for path in _all_decision_paths():
        text = path.read_text(encoding="utf-8")
        title = _title_from_markdown(text, path.stem)
        context = _section_text(text, "Context")
        decision = _section_text(text, "Decision")
        summary = (decision or context or "").split("\n")[0][:200]
        event_type = "milestone" if is_milestone(title, text) else "decision"
        events.append(
            {
                "date": _date_from_filename(path),
                "type": event_type,
                "title": title,
                "summary": summary or "(no summary)",
                "path": str(path.relative_to(MEMORY_ROOT.parent)),
                "sort_key": path.stat().st_mtime,
            }
        )

    for path in _all_incident_paths():
        text = path.read_text(encoding="utf-8")
        title = _title_from_markdown(text, path.stem)
        symptoms = _section_text(text, "Symptoms")
        events.append(
            {
                "date": _date_from_filename(path),
                "type": "incident",
                "title": title,
                "summary": (symptoms.split("\n")[0] if symptoms else "(no symptoms)")[:200],
                "path": str(path.relative_to(MEMORY_ROOT.parent)),
                "sort_key": path.stat().st_mtime,
            }
        )

    if LATEST_STATUS.exists():
        text = LATEST_STATUS.read_text(encoding="utf-8")
        events.append(
            {
                "date": _date_from_filename(LATEST_STATUS),
                "type": "milestone",
                "title": "Latest Status updated",
                "summary": "project-memory/Latest_Status.md",
                "path": str(LATEST_STATUS.relative_to(MEMORY_ROOT.parent)),
                "sort_key": LATEST_STATUS.stat().st_mtime,
            }
        )

    events.sort(key=lambda e: e["sort_key"], reverse=True)
    for e in events[:limit]:
        e.pop("sort_key", None)
    return events[:limit]


def fetch_incident_analytics() -> dict[str, Any]:
    items: list[tuple[str, str, str]] = []
    for path in _all_incident_paths():
        text = path.read_text(encoding="utf-8")
        title = _title_from_markdown(text, path.stem)
        items.append((title, text, str(path)))
    return aggregate_categories(items, classify_incident)


def fetch_decision_categories() -> dict[str, Any]:
    items: list[tuple[str, str, str]] = []
    for path in _all_decision_paths():
        text = path.read_text(encoding="utf-8")
        title = _title_from_markdown(text, path.stem)
        items.append((title, text, str(path)))
    return aggregate_categories(items, classify_decision)


def fetch_memory_analytics() -> dict[str, Any]:
    """Return Memory Analytics payload for dashboard (Phase 1.95)."""
    if LATEST_JSON.exists():
        try:
            return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    try:
        return generate_report(write_daily=True)
    except OSError:
        return {
            "degraded": True,
            "memory_health": "UNKNOWN",
            "detail": "No metrics available yet",
            "memory_growth": {},
            "growth_7d": {},
            "growth_30d": {},
            "harness_statistics": {},
            "headroom_statistics": {},
            "agent_sessions": {},
        }