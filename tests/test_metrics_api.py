"""Tests for Metrics Interpreter API routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from dashboard.metrics_rules import interpret_queue_pressure
from tests.fixtures.seed_dashboard import seed_dashboard_db


@pytest.fixture
def seeded(tmp_path: Path) -> Path:
    archive = tmp_path / "ad_archive"
    db_path = tmp_path / "seeded.db"
    seed_dashboard_db(db_path, archive_dir=archive)
    return db_path


def test_interpret_queue_pressure_critical() -> None:
    result = interpret_queue_pressure(
        pending=600,
        processing=0,
        done=1000,
        dropped=5000,
        drop_ratio=5.0,
    )
    assert result["status"] == "critical"
    assert "Worker capacity" in result["interpretation"]


def test_metrics_summary_shape(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    with patch(
        "dashboard.metrics_api._prometheus_query",
        return_value=(True, None, {"status": "success", "data": {"result": []}}),
    ), patch(
        "dashboard.metrics_api._prometheus_query_map",
        return_value=(True, {}, {"status": "success", "data": {"result": []}}),
    ):
        response = client.get("/api/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "overall_status" in data
    assert "sections" in data
    assert len(data["sections"]) == 6
    keys = {section["key"] for section in data["sections"]}
    assert "queue_pressure" in keys
    assert "gpu_health" in keys


def test_metrics_prometheus_allowlist(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    with patch(
        "dashboard.metrics_api._prometheus_query",
        return_value=(True, 42.0, {"status": "success"}),
    ):
        response = client.get("/api/metrics/prometheus?key=queue_depth")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "queue_depth"
    assert data["value"] == 42.0


def test_metrics_prometheus_rejects_unknown_key(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    response = client.get("/api/metrics/prometheus?key=evil_query")
    assert response.status_code == 400


def test_metrics_grafana_links(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    response = client.get("/api/metrics/grafana-links")
    assert response.status_code == 200
    data = response.json()
    assert data["base_url"].startswith("http")
    assert len(data["dashboards"]) >= 3
    assert len(data["panels"]) >= 5
