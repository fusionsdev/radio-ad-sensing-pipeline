"""Observability harness — Memory OS metrics collection and report health."""

from __future__ import annotations

from pathlib import Path

from tools.harness.lib.common import CheckResult, HarnessResult
from tools.memory.metrics_collector import DAILY_DIR, METRICS_ROOT, ensure_metrics_dirs
from tools.memory.metrics_report import (
    FRESHNESS_DAYS,
    LATEST_JSON,
    LATEST_MD,
    generate_report,
    metrics_freshness_status,
)


def run() -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict = {}

    ensure_metrics_dirs()
    metrics_dir_ok = METRICS_ROOT.is_dir()
    checks.append(
        CheckResult(
            name="metrics_directory",
            passed=metrics_dir_ok,
            detail=str(METRICS_ROOT) if metrics_dir_ok else "project-memory/Metrics/ missing",
            recommended_action=None if metrics_dir_ok else "Run metrics collector to create Metrics/",
        )
    )

    subdirs_ok = all((METRICS_ROOT / name).is_dir() for name in ("Daily", "Weekly", "Monthly"))
    checks.append(
        CheckResult(
            name="metrics_subdirs",
            passed=subdirs_ok,
            detail="Daily/Weekly/Monthly present" if subdirs_ok else "missing Metrics subdirectories",
            recommended_action=None if subdirs_ok else "Create Metrics/Daily, Weekly, Monthly",
        )
    )

    report_ok = False
    report_detail = ""
    try:
        payload = generate_report(write_daily=True)
        report_ok = bool(payload.get("collected_at"))
        report_detail = f"Latest.json written ({payload.get('date')})"
    except OSError as exc:
        report_detail = str(exc)
    checks.append(
        CheckResult(
            name="analytics_report",
            passed=report_ok,
            detail=report_detail if report_ok else f"report generation failed: {report_detail}",
            recommended_action=None if report_ok else "Fix tools/memory/metrics_report.py",
        )
    )

    freshness = metrics_freshness_status()
    checks.append(
        CheckResult(
            name="metrics_freshness",
            passed=freshness["status"] != "fail",
            detail=freshness["detail"],
            recommended_action=None
            if freshness["passed"]
            else f"Regenerate metrics (>{FRESHNESS_DAYS}d stale)",
        )
    )

    collector_ok = (METRICS_ROOT / "Daily").is_dir() and LATEST_JSON.exists() and LATEST_MD.exists()
    checks.append(
        CheckResult(
            name="metrics_files",
            passed=collector_ok,
            detail="Latest.json + Latest.md present" if collector_ok else "missing Latest metrics files",
            recommended_action=None if collector_ok else "Run python -m tools.memory.metrics_report",
        )
    )

    daily_count = len(list(DAILY_DIR.glob("*-metrics.json"))) if DAILY_DIR.exists() else 0
    hard_fail = not metrics_dir_ok or not report_ok
    warning = freshness["status"] == "warning"

    if hard_fail:
        overall = "fail"
    elif warning:
        overall = "warning"
    else:
        overall = "pass"

    metrics.update(
        {
            "observability_status": overall,
            "metrics_fresh": freshness["passed"],
            "analytics_report_ok": report_ok,
            "daily_snapshots": daily_count,
            "latest_json": str(LATEST_JSON.relative_to(METRICS_ROOT.parent.parent)),
        }
    )

    passed = overall != "fail"
    return HarnessResult(harness="observability", passed=passed, checks=checks, metrics=metrics)