"""Memory harness — validate project-memory vault health."""

from __future__ import annotations

from tools.harness.lib.common import CheckResult, HarnessResult
from tools.memory.memory_report import build_memory_health


def run() -> HarnessResult:
    health = build_memory_health()
    checks: list[CheckResult] = []

    core = health["core_files"]
    checks.append(
        CheckResult(
            name="core_files",
            passed=core["passed"],
            detail="all mandatory files present" if core["passed"] else f"missing: {core['missing']}",
            recommended_action=None
            if core["passed"]
            else "Create missing files in project-memory/",
        )
    )

    freshness = health["freshness"]
    checks.append(
        CheckResult(
            name="freshness",
            passed=freshness["passed"],
            detail=freshness["detail"],
            recommended_action=None
            if freshness["status"] != "fail"
            else "Create or update project-memory/Latest_Status.md",
        )
    )

    empty = health["empty_sections"]
    checks.append(
        CheckResult(
            name="empty_sections",
            passed=empty["passed"],
            detail="none" if empty["passed"] else "; ".join(empty["issues"][:10]),
            recommended_action=None if empty["passed"] else "Fill empty vault sections",
        )
    )

    links = health["broken_links"]
    checks.append(
        CheckResult(
            name="broken_links",
            passed=links["passed"],
            detail="none" if links["passed"] else "; ".join(links["broken"][:10]),
            recommended_action=None if links["passed"] else "Fix or create wikilink targets",
        )
    )

    # Hard-fail only on core, empty sections, broken links — freshness is warning-only
    hard_pass = core["passed"] and empty["passed"] and links["passed"]
    metrics = {
        "memory_health": health,
        "subchecks": health["subchecks"],
        "freshness_warning": health["subchecks"]["freshness"] == "warning",
    }

    return HarnessResult(
        harness="memory",
        passed=hard_pass,
        checks=checks,
        metrics=metrics,
    )