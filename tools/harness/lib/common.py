"""Shared harness utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MEMORY_ROOT = PROJECT_ROOT / "project-memory"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"

MANDATORY_MEMORY_FILES = [
    MEMORY_ROOT / "00_Project_Overview.md",
    MEMORY_ROOT / "01_Current_Architecture.md",
    MEMORY_ROOT / "02_Operating_Policy.md",
    MEMORY_ROOT / "03_Forbidden_Assumptions.md",
    MEMORY_ROOT / "04_Agent_Load_Order.md",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    recommended_action: str | None = None


@dataclass
class HarnessResult:
    harness: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_yaml_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "cases" in data:
        return list(data["cases"])
    return []


def build_report(results: list[HarnessResult]) -> dict[str, Any]:
    failed = [c for r in results for c in r.failed_checks()]
    all_passed = all(r.passed for r in results)
    overnight_ready = all_passed and not any(
        r.harness == "self_healing" and r.metrics.get("unhealthy_count", 0) > 0
        for r in results
    )
    actions = [c.recommended_action for c in failed if c.recommended_action]

    memory_result = next((r for r in results if r.harness == "memory"), None)
    memory_health: dict[str, Any] = {}
    if memory_result and "memory_health" in memory_result.metrics:
        memory_health = memory_result.metrics["memory_health"]

    headroom_result = next((r for r in results if r.harness == "headroom"), None)
    headroom_status: dict[str, Any] = {}
    if headroom_result:
        headroom_status = dict(headroom_result.metrics)

    observability_result = next((r for r in results if r.harness == "observability"), None)
    observability_status: dict[str, Any] = {}
    if observability_result:
        observability_status = dict(observability_result.metrics)

    return {
        "timestamp": utc_now_iso(),
        "status": "pass" if all_passed else "fail",
        "overnight_readiness": "ready" if overnight_ready else "not_ready",
        "harnesses": {r.harness: {"passed": r.passed, "metrics": r.metrics} for r in results},
        "memory_health": memory_health,
        "headroom_status": headroom_status,
        "observability_status": observability_status,
        "failed_checks": [
            {"harness": r.harness, "check": c.name, "detail": c.detail}
            for r in results
            for c in r.failed_checks()
        ],
        "recommended_actions": actions,
    }


def write_reports(report: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "latest.json"
    md_path = REPORTS_DIR / "latest.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Harness Report",
        "",
        f"**Timestamp:** {report['timestamp']}",
        f"**Status:** {report['status']}",
        f"**Overnight readiness:** {report['overnight_readiness']}",
        "",
    ]
    if report["failed_checks"]:
        lines.append("## Failed checks")
        for item in report["failed_checks"]:
            lines.append(f"- **{item['harness']}** / {item['check']}: {item['detail']}")
        lines.append("")
    if report["recommended_actions"]:
        lines.append("## Recommended actions")
        for action in report["recommended_actions"]:
            lines.append(f"- {action}")
        lines.append("")
    memory_health = report.get("memory_health") or {}
    if memory_health:
        from tools.memory.memory_report import format_memory_health_section  # noqa: PLC0415

        lines.extend(format_memory_health_section(memory_health))
    headroom_status = report.get("headroom_status") or {}
    if headroom_status:
        from tools.harness.runners.headroom_harness import format_headroom_status_section  # noqa: PLC0415

        lines.extend(format_headroom_status_section(headroom_status))
    observability_status = report.get("observability_status") or {}
    if observability_status:
        from tools.memory.metrics_report import format_observability_section  # noqa: PLC0415

        lines.extend(format_observability_section(observability_status))
    lines.append("## Harness summary")
    for name, info in report["harnesses"].items():
        status = "pass" if info["passed"] else "fail"
        lines.append(f"- **{name}**: {status}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def result_to_dict(result: HarnessResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["failed_count"] = len(result.failed_checks())
    return payload