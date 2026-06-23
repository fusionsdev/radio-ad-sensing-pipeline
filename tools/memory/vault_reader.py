"""Read-only parsers for project-memory vault and harness reports."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.harness.lib.common import REPORTS_DIR
from tools.memory._common import DECISIONS_DIR, INCIDENTS_DIR, MEMORY_ROOT, STATIONS_DIR
from tools.memory.memory_report import FRESHNESS_DAYS, LATEST_STATUS, build_memory_health

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