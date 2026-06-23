"""Dashboard harness — probe JSON APIs with seeded test DB (no production DB)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tools.harness.lib.common import CheckResult, HarnessResult, PROJECT_ROOT

PROBES = [
    ("/api/health", 200),
    ("/api/stations?limit=100", 200),
    ("/api/detections?limit=50", 200),
    ("/api/harvest/status", 200),
]


def _seed_db(db_path: Path, archive_dir: Path) -> None:
    from tests.fixtures.seed_dashboard import seed_dashboard_db  # noqa: PLC0415

    seed_dashboard_db(db_path, archive_dir=archive_dir)


def _create_test_client(db_path: Path) -> TestClient:
    from dashboard.main import create_app  # noqa: PLC0415

    return TestClient(create_app(db_path=db_path))


def run() -> HarnessResult:
    checks: list[CheckResult] = []
    metrics: dict = {"probes": []}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "ad_archive"
        db_path = tmp_path / "harness.db"
        try:
            _seed_db(db_path, archive)
            client = _create_test_client(db_path)
        except Exception as exc:  # noqa: BLE001
            return HarnessResult(
                harness="dashboard",
                passed=False,
                checks=[
                    CheckResult(
                        name="setup",
                        passed=False,
                        detail=str(exc),
                        recommended_action="Fix dashboard seed or create_app wiring",
                    )
                ],
            )

        for route, expected_status in PROBES:
            response = client.get(route)
            ok = response.status_code == expected_status
            metrics["probes"].append({"route": route, "status": response.status_code, "ok": ok})
            checks.append(
                CheckResult(
                    name=f"probe_{route}",
                    passed=ok,
                    detail=f"status={response.status_code}" if ok else f"expected {expected_status}, got {response.status_code}",
                    recommended_action=None
                    if ok
                    else f"Fix dashboard route {route} in dashboard/main.py or routers",
                )
            )

            if ok and route == "/api/health":
                body = response.json()
                db_ok = bool(body.get("db_reachable"))
                checks.append(
                    CheckResult(
                        name="health_db_reachable",
                        passed=db_ok,
                        detail=f"db_reachable={body.get('db_reachable')}",
                        recommended_action=None if db_ok else "Ensure fetch_health returns db_reachable on seeded DB",
                    )
                )

    passed = all(c.passed for c in checks)
    return HarnessResult(harness="dashboard", passed=passed, checks=checks, metrics=metrics)