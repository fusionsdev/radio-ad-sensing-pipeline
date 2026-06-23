"""Tests for RadioSense system control proxy routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from tests.fixtures.seed_dashboard import seed_dashboard_db


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    archive = tmp_path / "ad_archive"
    db_path = tmp_path / "seeded.db"
    seed_dashboard_db(db_path, archive_dir=archive)
    return TestClient(create_app(db_path=db_path))


def test_system_status_merges_control_bridge(client: TestClient) -> None:
    control_payload = {
        "ok": True,
        "startup_command": "test-command",
        "components": {
            "checked_at": "2026-06-22T12:00:00Z",
            "hermes_bridge": {"status": "online"},
            "frontend": {"status": "running"},
            "docker_dashboard": {"status": "healthy"},
        },
        "recent_actions": [{"line": "action=test"}],
    }
    with patch("dashboard.routes.system.system_client.fetch_control_status", return_value=control_payload):
        response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["control_bridge_online"] is True
    assert data.get("failure_class")
    assert data.get("recommended_action") is not None
    assert isinstance(data.get("safe_actions"), list)
    assert isinstance(data.get("components"), dict)
    assert any(row["key"] == "backend_api" for row in data["rows"])
    assert any(row["key"] == "harvest" for row in data["rows"])


def test_system_status_control_bridge_offline(client: TestClient) -> None:
    offline = {
        "ok": False,
        "error": "RadioSense control bridge is offline",
        "recommended_command": "start bridge",
    }
    with patch("dashboard.routes.system.system_client.fetch_control_status", return_value=offline):
        response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["control_bridge_online"] is False
    assert data["recommended_command"] == "start bridge"


def test_system_action_proxies_bridge(client: TestClient) -> None:
    with patch(
        "dashboard.routes.system.system_client.run_control_action",
        return_value={"ok": True, "action": "start-hermes-bridge", "message": "started"},
    ):
        response = client.post("/api/system/action/start-hermes-bridge")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_system_action_unknown_returns_404(client: TestClient) -> None:
    response = client.post("/api/system/action/run-arbitrary-shell")
    assert response.status_code == 404


def test_system_action_restart_dashboard_proxied(client: TestClient) -> None:
    with patch(
        "dashboard.routes.system.system_client.run_control_action",
        return_value={
            "ok": True,
            "action": "restart-dashboard",
            "started_at": "2026-06-22T12:00:00Z",
            "finished_at": "2026-06-22T12:00:10Z",
            "stdout_tail": "Started",
            "stderr_tail": "",
            "next_check_in_seconds": 10,
        },
    ):
        response = client.post("/api/system/action/restart-dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "restart-dashboard"
    assert body["next_check_in_seconds"] == 10


def test_system_action_offline_returns_503(client: TestClient) -> None:
    with patch(
        "dashboard.routes.system.system_client.run_control_action",
        return_value={
            "ok": False,
            "error": "RadioSense control bridge is offline",
            "recommended_command": "start bridge",
        },
    ):
        response = client.post("/api/system/action/restart-dashboard")
    assert response.status_code == 503