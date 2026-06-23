"""Tests for read-only Memory OS API routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from tests.fixtures.seed_dashboard import seed_dashboard_db


@pytest.fixture
def memory_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "memory_api.db"
    seed_dashboard_db(db_path, archive_dir=tmp_path / "archive")
    return TestClient(create_app(db_path=db_path))


def test_memory_health_returns_200(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert body["status"] in {"PASS", "WARNING", "FAIL"}
    for key in ("core_files", "runbooks", "stations", "decisions", "freshness", "links"):
        assert key in body


def test_memory_status_returns_200(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/status")
    assert response.status_code == 200
    body = response.json()
    assert "latest_status_age_days" in body
    assert "freshness_threshold_days" in body


def test_memory_harness_latest_returns_200(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/harness/latest")
    assert response.status_code == 200
    body = response.json()
    assert "source" in body
    assert body["source"] in {"json", "md", "none"}


def test_memory_decisions_returns_rows(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/decisions?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert isinstance(body["rows"], list)
    if body["rows"]:
        row = body["rows"][0]
        assert {"date", "title", "summary", "path"} <= set(row.keys())


def test_memory_incidents_returns_rows(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/incidents?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["rows"], list)


def test_memory_stations_returns_rows(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/stations?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["rows"], list)


def test_memory_analytics_returns_200(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/analytics")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "memory_growth",
        "growth_7d",
        "harness_statistics",
        "headroom_statistics",
    ):
        assert key in body


def test_memory_metrics_returns_200(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/metrics")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "total_decisions",
        "total_incidents",
        "total_station_changes",
        "total_runbooks",
        "total_harness_runs",
        "memory_growth_7d",
    ):
        assert key in body


def test_memory_timeline_returns_rows(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/timeline?limit=20")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["rows"], list)
    if body["rows"]:
        assert {"date", "type", "title", "summary", "path"} <= set(body["rows"][0].keys())


def test_memory_incident_analytics(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/incidents/analytics")
    assert response.status_code == 200
    body = response.json()
    assert "categories" in body
    assert "total" in body


def test_memory_decision_categories(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/decisions/categories")
    assert response.status_code == 200
    body = response.json()
    assert "categories" in body
    assert body["total"] >= 0