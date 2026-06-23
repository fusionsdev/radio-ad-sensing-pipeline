"""Decision harness — fail on undocumented behavioral changes."""

from __future__ import annotations

from tools.harness.lib.common import CheckResult, HarnessResult
from tools.memory.behavior import (
    changed_components,
    ensure_baseline,
    find_covering_decisions,
    sync_baseline_after_documented_changes,
    undocumented_changes,
)


def run() -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict = {}

    ensure_baseline()
    changes = changed_components()
    metrics["changed_components"] = [c["component"] for c in changes]
    metrics["change_count"] = len(changes)

    if not changes:
        checks.append(
            CheckResult(
                name="behavior_documented",
                passed=True,
                detail="no behavioral drift from baseline",
            )
        )
        return HarnessResult(harness="decision", passed=True, checks=checks, metrics=metrics)

    coverage = find_covering_decisions(changes)
    undocumented = undocumented_changes(changes)
    metrics["documented"] = {k: [str(p.name) for p in v] for k, v in coverage.items()}
    metrics["undocumented"] = [c["component"] for c in undocumented]

    if undocumented:
        detail_parts = [
            f"{c['component']} (files: {', '.join(c['files'])})" for c in undocumented
        ]
        checks.append(
            CheckResult(
                name="behavior_documented",
                passed=False,
                detail="undocumented changes: " + "; ".join(detail_parts),
                recommended_action=(
                    "Run tools/memory/decision_logger.py for each change, "
                    "or add a decision under project-memory/Decisions/ referencing affected files"
                ),
            )
        )
    else:
        sync_baseline_after_documented_changes(changes)
        checks.append(
            CheckResult(
                name="behavior_documented",
                passed=True,
                detail=f"documented changes: {', '.join(c['component'] for c in changes)}",
            )
        )

    passed = all(c.passed for c in checks)
    return HarnessResult(harness="decision", passed=passed, checks=checks, metrics=metrics)