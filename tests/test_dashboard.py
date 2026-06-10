"""Tests for the read-only FastAPI dashboard."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard import queries
from dashboard.main import create_app
from shared.db import get_connection, migrate
from tests.fixtures.seed_dashboard import seed_dashboard_db

HTML_ROUTES = ["/", "/ads", "/stations", "/gaps"]


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, int]]:
    archive = tmp_path / "ad_archive"
    monkeypatch.setattr(queries, "AD_ARCHIVE_DIR", archive)
    db_path = tmp_path / "seeded.db"
    ids = seed_dashboard_db(db_path, archive_dir=archive)
    return db_path, ids


@pytest.fixture
def missing_db(tmp_path: Path) -> Path:
    return tmp_path / "does-not-exist.db"


def test_all_html_routes_200_on_empty_db(empty_db: Path) -> None:
    client = TestClient(create_app(db_path=empty_db))
    for route in HTML_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route


def test_all_html_routes_200_on_seeded_db(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    client = TestClient(create_app(db_path=db_path))
    for route in HTML_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route


def test_ad_detail_200_seeded(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, ids = seeded
    client = TestClient(create_app(db_path=db_path))
    response = client.get(f"/ads/{ids['ad_id']}")
    assert response.status_code == 200
    assert "Acme Funding" in response.text


def test_ad_detail_404_unknown(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    client = TestClient(create_app(db_path=db_path))
    assert client.get("/ads/9999").status_code == 404


def test_missing_db_shows_no_database_page(missing_db: Path) -> None:
    client = TestClient(create_app(db_path=missing_db))
    response = client.get("/")
    assert response.status_code == 200
    assert "No database yet" in response.text


def test_health_json_empty_db(empty_db: Path) -> None:
    client = TestClient(create_app(db_path=empty_db))
    data = client.get("/health").json()
    assert data["db_reachable"] is True
    assert data["pending_count"] == 0


def test_health_json_missing_db(missing_db: Path) -> None:
    client = TestClient(create_app(db_path=missing_db))
    data = client.get("/health").json()
    assert data["db_reachable"] is False


def test_health_pending_count_seeded(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    client = TestClient(create_app(db_path=db_path))
    data = client.get("/health").json()
    assert data["db_reachable"] is True
    assert data["pending_count"] == 1


def test_audio_serves_seeded_file(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, ids = seeded
    client = TestClient(create_app(db_path=db_path))
    response = client.get(f"/audio/{ids['ad_id']}")
    assert response.status_code == 200
    assert "audio" in response.headers.get("content-type", "")


def test_audio_path_traversal_rejected(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE canonical_ads SET archived_audio_path = ? WHERE id = 1",
            ("../../etc/passwd",),
        )
        conn.commit()
    finally:
        conn.close()
    client = TestClient(create_app(db_path=db_path))
    assert client.get("/audio/1").status_code == 404


def test_audio_missing_db(missing_db: Path) -> None:
    client = TestClient(create_app(db_path=missing_db))
    assert client.get("/audio/1").status_code == 404


def test_dashboard_never_opens_writable_connection(
    seeded: tuple[Path, dict[str, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path, ids = seeded
    import shared.db as shared_db

    original = shared_db.get_connection

    def strict_get_connection(path, *, read_only: bool = False):
        if not read_only:
            raise AssertionError("Dashboard must use read_only=True")
        return original(path, read_only=read_only)

    # Patch both the module binding used by dashboard.queries and shared.db itself.
    monkeypatch.setattr(shared_db, "get_connection", strict_get_connection)
    monkeypatch.setattr(queries, "get_connection", strict_get_connection)
    client = TestClient(create_app(db_path=db_path))
    for route in HTML_ROUTES + ["/health", f"/ads/{ids['ad_id']}", f"/audio/{ids['ad_id']}"]:
        response = client.get(route)
        assert response.status_code in {200, 404}


def test_derive_station_status() -> None:
    now = 1_000_000.0
    down = 15 * 60
    assert queries.derive_station_status(
        enabled=False, last_chunk_ts=now - 30, now=now, down_threshold_seconds=down
    ) == "disabled"
    assert queries.derive_station_status(
        enabled=True, last_chunk_ts=None, now=now, down_threshold_seconds=down
    ) == "waiting"
    assert queries.derive_station_status(
        enabled=True, last_chunk_ts=now - 60, now=now, down_threshold_seconds=down
    ) == "live"
    assert queries.derive_station_status(
        enabled=True, last_chunk_ts=now - 200, now=now, down_threshold_seconds=down
    ) == "stale"
    assert queries.derive_station_status(
        enabled=True, last_chunk_ts=now - 1200, now=now, down_threshold_seconds=down
    ) == "down"


def test_stations_page_shows_status_column(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    client = TestClient(create_app(db_path=db_path))
    response = client.get("/stations")
    assert response.status_code == 200
    assert "<th>Status</th>" in response.text
    assert 'class="badge' in response.text


def test_overview_shows_status_column(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    client = TestClient(create_app(db_path=db_path))
    response = client.get("/")
    assert response.status_code == 200
    assert "<th>Status</th>" in response.text
    assert 'class="badge' in response.text


def test_ads_htmx_partial(seeded: tuple[Path, dict[str, int]]) -> None:
    db_path, _ = seeded
    client = TestClient(create_app(db_path=db_path))
    response = client.get("/ads", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "Acme Funding" in response.text
    assert "<html" not in response.text.lower()
