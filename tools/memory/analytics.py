"""Read-only categorization and aggregation for Memory OS analytics."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tools.harness.lib.common import REPORTS_DIR
from tools.memory._common import (
    DECISIONS_DIR,
    INCIDENTS_DIR,
    MEMORY_ROOT,
    RUNBOOKS_DIR,
    STATIONS_DIR,
    find_markdown_files,
)

INCIDENT_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Dashboard": ("dashboard", "api 404", "/api/", "memory page", "ui"),
    "API": ("api ", "endpoint", "500", "404", "json"),
    "Docker": ("docker", "container", "image", "compose", "radio-dashboard"),
    "Station": ("station", "stream", "ingestor", "rotate", "kfi", "wbap"),
    "Memory OS": ("memory os", "project-memory", "vault", "harness", "obsidian"),
}

DECISION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Operations": ("ops", "operator", "runbook", "pipeline ops", "harvest"),
    "Classifier": ("classifier", "loan_classifier", "loan detection", "loan pattern"),
    "Station Policy": ("station", "rotation", "stations.yaml", "keep", "watch", "rotate"),
    "Dashboard": ("dashboard", "routing", "radiosense", "aistudio", "memory dashboard"),
    "Infrastructure": ("docker", "compose", "prometheus", "grafana", "deploy"),
    "Memory OS": ("memory os", "project-memory", "phase 1", "phase 1.5", "phase 1.8", "zvec"),
}

MILESTONE_KEYWORDS = ("phase", "memory os", "milestone", "shipped")


def _text_blob(*parts: str) -> str:
    return " ".join(p.lower() for p in parts if p)


def classify_incident(title: str, text: str) -> str:
    blob = _text_blob(title, text)
    scores: list[tuple[int, str]] = []
    for category, keywords in INCIDENT_CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in blob)
        if score:
            scores.append((score, category))
    if not scores:
        return "Other"
    scores.sort(reverse=True)
    return scores[0][1]


def classify_decision(title: str, text: str) -> str:
    blob = _text_blob(title, text)
    scores: list[tuple[int, str]] = []
    for category, keywords in DECISION_CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in blob)
        if score:
            scores.append((score, category))
    if not scores:
        return "Operations"
    scores.sort(reverse=True)
    return scores[0][1]


def is_milestone(title: str, text: str) -> bool:
    blob = _text_blob(title, text)
    return any(kw in blob for kw in MILESTONE_KEYWORDS)


def _mtime_days_ago(path: Path) -> float:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return (datetime.now(tz=UTC) - mtime).total_seconds() / 86400


def count_vault_growth(days: int = 7) -> int:
    if not MEMORY_ROOT.exists():
        return 0
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    count = 0
    for path in find_markdown_files(MEMORY_ROOT):
        if ".obsidian" in path.parts or ".smart-env" in path.parts:
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if mtime >= cutoff:
            count += 1
    return count


def count_station_history_entries() -> int:
    if not STATIONS_DIR.exists():
        return 0
    history_re = re.compile(
        r"^\-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s+—\s+(\w+):",
        re.MULTILINE,
    )
    total = 0
    for path in STATIONS_DIR.glob("*.md"):
        if path.name.lower() == "batch policy.md":
            continue
        text = path.read_text(encoding="utf-8")
        total += len(history_re.findall(text))
    return total


def count_harness_report_files() -> int:
    if not REPORTS_DIR.exists():
        return 0
    return len(list(REPORTS_DIR.glob("*.json")))


def aggregate_categories(
    items: list[tuple[str, str, str]],
    classifier,
) -> dict[str, Any]:
    """items: (title, text, path)"""
    counts: dict[str, int] = {}
    for title, text, _path in items:
        cat = classifier(title, text)
        counts[cat] = counts.get(cat, 0) + 1
    categories = [{"category": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return {"categories": categories, "total": len(items)}