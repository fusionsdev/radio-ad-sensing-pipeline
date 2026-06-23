#!/usr/bin/env python3
"""Run all RadioSense harness checks and write reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is importable when invoked as script
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.harness.lib.common import build_report, write_reports  # noqa: E402
from tools.harness.runners import (  # noqa: E402
    classifier_harness,
    dashboard_harness,
    hermes_harness,
    self_healing_harness,
    station_harness,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RadioSense harness — verify classifier, dashboard, ops context")
    parser.add_argument(
        "--execute-self-heal",
        action="store_true",
        help="Restart unhealthy/exited Docker services (default: report only)",
    )
    args = parser.parse_args(argv)

    results = [
        classifier_harness.run(),
        dashboard_harness.run(),
        self_healing_harness.run(execute_self_heal=args.execute_self_heal),
        station_harness.run(),
        hermes_harness.run(),
    ]

    report = build_report(results)
    write_reports(report)

    print(f"Harness status: {report['status']}")
    print(f"Overnight readiness: {report['overnight_readiness']}")
    print(f"Report: tools/harness/reports/latest.md")

    if report["failed_checks"]:
        print("\nFailed checks:")
        for item in report["failed_checks"]:
            print(f"  - [{item['harness']}] {item['check']}: {item['detail']}")

    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())