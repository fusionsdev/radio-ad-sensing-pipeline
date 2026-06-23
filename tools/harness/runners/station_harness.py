"""Station rotation harness — verify keep / watch / rotate_out logic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tools.harness.lib.common import PROJECT_ROOT, CheckResult, HarnessResult, load_yaml_cases

CASES_PATH = Path(__file__).resolve().parents[1] / "cases" / "station_rotation_cases.yaml"


def _rotation_decision(unique_loan_advertisers: int, total_ads: int, irrelevant_count: int) -> str:
    """Mirror scripts/station_rotation.py decision logic."""
    if unique_loan_advertisers >= 2:
        return "keep"
    if unique_loan_advertisers == 1:
        return "watch"
    if total_ads > 0 and irrelevant_count == total_ads:
        return "rotate_out"
    return "rotate_out"


def _load_classifier():
    script = PROJECT_ROOT / "scripts" / "loan_classifier.py"
    spec = importlib.util.spec_from_file_location("loan_classifier_station", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run() -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict = {}

    cases = load_yaml_cases(CASES_PATH)
    if not cases:
        return HarnessResult(
            harness="station",
            passed=False,
            checks=[
                CheckResult(
                    name="cases_loaded",
                    passed=False,
                    detail=f"missing or empty {CASES_PATH.name}",
                    recommended_action="Add station rotation fixture cases",
                )
            ],
        )

    rotation_cases = [c for c in cases if "expected_decision" in c]
    failed: list[str] = []
    for case in rotation_cases:
        case_id = case.get("id", "unknown")
        unique = int(case.get("unique_loan_advertisers", 0))
        total = int(case.get("total_ads", 0))
        irrelevant = int(case.get("irrelevant_ads", total))
        expected = case.get("expected_decision", "")
        actual = _rotation_decision(unique, total, irrelevant)
        if actual != expected:
            failed.append(f"{case_id}: got {actual}, want {expected}")

    checks.append(
        CheckResult(
            name="rotation_logic",
            passed=len(failed) == 0,
            detail="all cases pass" if not failed else "; ".join(failed),
            recommended_action=None if not failed else "Align station_rotation.py with fixture expectations",
        )
    )

    classifier_cases = [c for c in cases if "company" in c]
    if classifier_cases:
        lc = _load_classifier()
        cls_failed: list[str] = []
        for case in classifier_cases:
            result = lc.classify_loan(
                company=case.get("company", ""),
                offer=case.get("offer", ""),
                text=case.get("text", ""),
            )
            if result["is_loan"] != bool(case.get("expect_loan")):
                cls_failed.append(str(case.get("id")))
        checks.append(
            CheckResult(
                name="classifier_integration",
                passed=len(cls_failed) == 0,
                detail="ok" if not cls_failed else f"failed: {', '.join(cls_failed)}",
            )
        )

    try:
        import yaml  # noqa: PLC0415

        stations_path = PROJECT_ROOT / "config" / "stations.yaml"
        stations_doc = yaml.safe_load(stations_path.read_text(encoding="utf-8"))
        enabled = [s["name"] for s in stations_doc.get("stations", []) if s.get("enabled")]
        metrics["enabled_count"] = len(enabled)
        metrics["enabled_stations"] = enabled
        checks.append(
            CheckResult(
                name="stations_yaml_parseable",
                passed=True,
                detail=f"{len(enabled)} enabled station(s)",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            CheckResult(
                name="stations_yaml_parseable",
                passed=False,
                detail=str(exc),
                recommended_action="Fix config/stations.yaml syntax",
            )
        )

    passed = all(c.passed for c in checks)
    return HarnessResult(harness="station", passed=passed, checks=checks, metrics=metrics)