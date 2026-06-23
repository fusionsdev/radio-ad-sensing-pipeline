"""Tests for RadioSense system health classifier."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dashboard import system_health


def test_classify_partial_backend_failure() -> None:
    components = {
        "backend_health": {"ok": True, "db_reachable": True},
        "control_bridge": {"ok": True},
        "hermes_bridge": {"ok": True},
        "stations_api": {"ok": False, "status": 500, "error": "boom"},
        "detections_api": {"ok": True},
        "sse": {"ok": True},
    }
    overall, failure_class, action = system_health.classify_failure(components)
    assert overall == "critical"
    assert failure_class == "partial_backend_failure"
    assert action == "restart-dashboard"


def test_classify_db_unreachable() -> None:
    components = {
        "backend_health": {"ok": False, "db_reachable": False},
        "control_bridge": {"ok": True},
    }
    _, failure_class, action = system_health.classify_failure(components)
    assert failure_class == "db_unreachable"
    assert action == "restart-dashboard"


def test_safe_actions_without_control_bridge() -> None:
    actions = system_health.safe_actions_for("partial_backend_failure", control_bridge_online=False)
    assert "restart-dashboard" not in actions
    assert "export-report" in actions


def test_build_status_payload_marks_unhealthy(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    control_payload = {"ok": True, "components": {}, "recent_actions": []}
    with patch("dashboard.system_health.probe_all_components") as probe:
        probe.return_value = {
            "backend_health": {"ok": True, "db_reachable": True},
            "stations_api": {"ok": False, "status": 500, "error": "stations failed"},
            "detections_api": {"ok": True},
            "overview_api": {"ok": True},
            "harvest_status_api": {"ok": True},
            "queue_health_api": {"ok": True},
            "sse": {"ok": True},
            "hermes_bridge": {"ok": True},
            "control_bridge": {"ok": True},
        }
        payload = system_health.build_status_payload(db_path, control_payload)
    assert payload["ok"] is False
    assert payload["failure_class"] == "partial_backend_failure"
    assert "restart-dashboard" in payload["safe_actions"]