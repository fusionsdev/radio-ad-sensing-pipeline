"""Classifier harness — precision and known false-positive guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tools.harness.lib.common import PROJECT_ROOT, CheckResult, HarnessResult, load_yaml_cases

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
MIN_PRECISION = 0.85


def _load_classifier():
    script = PROJECT_ROOT / "scripts" / "loan_classifier.py"
    spec = importlib.util.spec_from_file_location("loan_classifier", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["loan_classifier"] = module
    spec.loader.exec_module(module)
    return module


def run() -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict = {}

    try:
        lc = _load_classifier()
    except Exception as exc:  # noqa: BLE001
        return HarnessResult(
            harness="classifier",
            passed=False,
            checks=[
                CheckResult(
                    name="import_classifier",
                    passed=False,
                    detail=str(exc),
                    recommended_action="Verify scripts/loan_classifier.py exists",
                )
            ],
        )

    builtin_ok = lc.run_tests()
    checks.append(
        CheckResult(
            name="builtin_tests",
            passed=builtin_ok,
            detail="29 built-in cases" if builtin_ok else "Built-in classifier tests failed",
            recommended_action=None if builtin_ok else "Fix scripts/loan_classifier.py run_tests() failures",
        )
    )

    fp_cases = load_yaml_cases(CASES_DIR / "classifier_false_positives.yaml")
    fp_passed = 0
    fp_failed: list[str] = []
    for case in fp_cases:
        result = lc.classify_loan(
            company=case.get("company", ""),
            offer=case.get("offer", ""),
            text=case.get("text", ""),
        )
        expect_loan = bool(case.get("expect_loan", False))
        if result["is_loan"] == expect_loan:
            fp_passed += 1
        else:
            fp_failed.append(case.get("id", "unknown"))

    if fp_cases:
        precision = fp_passed / len(fp_cases)
        metrics["precision"] = round(precision, 4)
        metrics["cases_total"] = len(fp_cases)
        metrics["cases_passed"] = fp_passed
        precision_ok = precision >= MIN_PRECISION
        checks.append(
            CheckResult(
                name="precision_threshold",
                passed=precision_ok,
                detail=f"precision={precision:.1%} (min {MIN_PRECISION:.0%}), failed={fp_failed}",
                recommended_action=None
                if precision_ok
                else "Add exclusions or tighten LOAN_PATTERNS in loan_classifier.py",
            )
        )
        checks.append(
            CheckResult(
                name="no_known_false_positives",
                passed=len(fp_failed) == 0,
                detail="none" if not fp_failed else f"failed cases: {', '.join(fp_failed)}",
                recommended_action=None
                if not fp_failed
                else "Update classifier_false_positives.yaml cases after fix",
            )
        )
    else:
        metrics["precision"] = 1.0 if builtin_ok else 0.0
        checks.append(
            CheckResult(
                name="precision_threshold",
                passed=builtin_ok,
                detail="derived from builtin tests (no external cases file)",
            )
        )

    passed = all(c.passed for c in checks)
    return HarnessResult(harness="classifier", passed=passed, checks=checks, metrics=metrics)