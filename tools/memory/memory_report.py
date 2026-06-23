"""Memory health report for harness and CLI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tools.harness.lib.common import MANDATORY_MEMORY_FILES
from tools.memory._common import (
    DECISIONS_DIR,
    INCIDENTS_DIR,
    MEMORY_ROOT,
    RUNBOOKS_DIR,
    STATIONS_DIR,
    empty_sections,
    find_markdown_files,
    parse_wikilinks,
    resolve_wikilink,
)

FRESHNESS_DAYS = 7
LATEST_STATUS = MEMORY_ROOT / "Latest_Status.md"


def _file_age_days(path: Path) -> float | None:
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return (datetime.now(tz=UTC) - mtime).total_seconds() / 86400


def check_core_files() -> dict[str, Any]:
    missing = [p.name for p in MANDATORY_MEMORY_FILES if not p.exists()]
    return {"passed": not missing, "missing": missing}


def check_freshness() -> dict[str, Any]:
    age = _file_age_days(LATEST_STATUS)
    if age is None:
        return {"passed": False, "status": "fail", "detail": "Latest_Status.md missing", "age_days": None}
    stale = age > FRESHNESS_DAYS
    return {
        "passed": True,
        "status": "warning" if stale else "pass",
        "detail": f"age={age:.1f}d (threshold {FRESHNESS_DAYS}d)",
        "age_days": round(age, 2),
    }


def check_empty_sections() -> dict[str, Any]:
    issues: list[str] = []

    for path in find_markdown_files(RUNBOOKS_DIR):
        empty = empty_sections(path.read_text(encoding="utf-8"))
        if empty:
            issues.append(f"runbook:{path.name}:{','.join(empty)}")

    for path in find_markdown_files(STATIONS_DIR):
        if path.name.lower() == "batch policy.md":
            continue
        empty = empty_sections(path.read_text(encoding="utf-8"))
        critical = [s for s in empty if s.lower() in {"history", "reasoning", "status"}]
        if critical:
            issues.append(f"station:{path.name}:{','.join(critical)}")

    for path in find_markdown_files(DECISIONS_DIR):
        empty = empty_sections(path.read_text(encoding="utf-8"))
        required = [s for s in empty if s.lower() in {"context", "decision"}]
        if required:
            issues.append(f"decision:{path.name}:{','.join(required)}")

    return {"passed": not issues, "issues": issues}


def check_broken_links() -> dict[str, Any]:
    broken: list[str] = []
    for path in find_markdown_files(MEMORY_ROOT):
        if ".obsidian" in path.parts or ".smart-env" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for target in parse_wikilinks(text):
            if not resolve_wikilink(target, path):
                rel = path.relative_to(MEMORY_ROOT)
                broken.append(f"{rel} → [[{target}]]")
    return {"passed": not broken, "broken": broken}


def build_memory_health() -> dict[str, Any]:
    core = check_core_files()
    freshness = check_freshness()
    empty = check_empty_sections()
    links = check_broken_links()

    subchecks = {
        "core_files": "pass" if core["passed"] else "fail",
        "runbooks": "pass" if empty["passed"] or not any(i.startswith("runbook:") for i in empty["issues"]) else "fail",
        "stations": "pass" if not any(i.startswith("station:") for i in empty["issues"]) else "fail",
        "decisions": "pass" if not any(i.startswith("decision:") for i in empty["issues"]) else "fail",
        "freshness": freshness["status"],
        "links": "pass" if links["passed"] else "fail",
    }

    hard_fail = not core["passed"] or not empty["passed"] or not links["passed"]
    return {
        "passed": not hard_fail,
        "status": "pass" if not hard_fail else "fail",
        "subchecks": subchecks,
        "core_files": core,
        "freshness": freshness,
        "empty_sections": empty,
        "broken_links": links,
        "vault_markdown_count": len(find_markdown_files(MEMORY_ROOT)),
        "incidents_count": len(find_markdown_files(INCIDENTS_DIR)),
    }


def format_memory_health_section(health: dict[str, Any]) -> list[str]:
    lines = [
        "## Memory Health",
        "",
        f"**Memory Health:** {health['status'].upper()}",
        "",
        f"- **Core Files:** {health['subchecks']['core_files'].upper()}",
        f"- **Runbooks:** {health['subchecks']['runbooks'].upper()}",
        f"- **Stations:** {health['subchecks']['stations'].upper()}",
        f"- **Decisions:** {health['subchecks']['decisions'].upper()}",
        f"- **Freshness:** {health['subchecks']['freshness'].upper()}",
        f"- **Links:** {health['subchecks']['links'].upper()}",
        "",
    ]
    if health["empty_sections"]["issues"]:
        lines.append("### Empty sections")
        for issue in health["empty_sections"]["issues"][:20]:
            lines.append(f"- {issue}")
        lines.append("")
    if health["broken_links"]["broken"]:
        lines.append("### Broken links")
        for link in health["broken_links"]["broken"][:20]:
            lines.append(f"- {link}")
        lines.append("")
    return lines