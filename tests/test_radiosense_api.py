"""Tests for RadioSense JSON API routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from tests.fixtures.seed_dashboard import seed_dashboard_db

RADIOSENSE_ROUTES = [
    "/api/overview",
    "/api/stations",
    "/api/detections?limit=5",
    "/api/keyword-candidates?limit=5",
    "/api/advertisers",
    "/api/exports",
    "/api/watchdog",
]


@pytest.fixture
def seeded(tmp_path: Path) -> Path:
    archive = tmp_path / "ad_archive"
    db_path = tmp_path / "seeded.db"
    seed_dashboard_db(db_path, archive_dir=archive)
    return db_path


def test_radiosense_routes_200(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    for route in RADIOSENSE_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.headers["content-type"].startswith("application/json"), route


def test_overview_shape(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    data = client.get("/api/overview").json()
    assert data["status"] in {"ok", "error"}
    assert "stations" in data
    assert "queue" in data
    assert "detections" in data
    assert "harvest" in data


def test_stations_rows(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    data = client.get("/api/stations").json()
    assert "rows" in data
    assert "count" in data


def test_advertiser_detail_not_found(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    response = client.get("/api/advertisers/999999")
    assert response.status_code == 404


def test_export_download_rejects_traversal(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    response = client.get("/api/exports/..%2Fpyproject.toml")
    assert response.status_code == 404


def test_live_events_sse(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    response = client.get("/api/live/events?once=true")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("data: ")
    assert "health" in response.text
