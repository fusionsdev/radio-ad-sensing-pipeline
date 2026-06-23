"""Tests for the Radio Harvest dashboard control panel and API.

Covers: fixed command allowlist, double-start guard, HTML route rendering,
JSON endpoints, and that POST actions wrap the CLI behind a monkeypatchable
subprocess seam (no real ffmpeg / real DB writes in tests).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard import harvest_api
from dashboard.main import create_app
from shared.db import migrate
from tests.fixtures.seed_dashboard import seed_dashboard_db


HARVEST_GET_ROUTES = [
    "/radio-harvest",
    "/radio-harvest/status",
    "/radio-harvest/detections",
    "/radio-harvest/queue",
    "/radio-harvest/stations",
]


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def seeded(tmp_path: Path) -> Path:
    archive = tmp_path / "ad_archive"
    db_path = tmp_path / "seeded.db"
    seed_dashboard_db(db_path, archive_dir=archive)
    return db_path


def _fake_runner(ok: bool = True, stdout: str = "", stderr: str = ""):
    calls: list[tuple[str, ...]] = []

    def _runner(argv):
        calls.append(argv)
        return {
            "ok": ok,
            "returncode": 0 if ok else 1,
            "stdout": stdout,
            "stderr": stderr,
        }

    _runner.calls = calls  # type: ignore[attr-defined]
    return _runner


# ---------------------------------------------------------------- allowlist


def test_allowed_actions_is_fixed_subset() -> None:
    assert set(harvest_api.allowed_actions()) == {"probe", "start", "stop", "status"}


def test_unknown_action_rejected() -> None:
    with pytest.raises(harvest_api.UnknownActionError):
        harvest_api.run_control_action("rm -rf /")
    with pytest.raises(harvest_api.UnknownActionError):
        harvest_api.run_control_action("export")  # not exposed via dashboard


def test_allowlist_argv_is_constant_no_user_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """No user/request data can become a shell argument — argv are fixed tuples."""
    captured: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        harvest_api, "_run_subprocess", lambda argv: captured.append(argv) or {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}
    )
    # Even if we tried to pass user input, run_control_action ignores it —
    # it only accepts a known action key and looks up the fixed argv.
    harvest_api.run_control_action("probe")
    assert captured[0] == harvest_api.ALLOWED_COMMANDS["probe"]
    # argv must contain the fixed script + limit — no room for user input
    assert any("harvest_control.py" in part for part in captured[0])
    assert "--limit" in captured[0]
    assert "20" in captured[0]


# --------------------------------------------------------- double-start guard


def test_start_blocked_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harvest_api, "read_status_file", lambda: {"state": "running"})
    runner = _fake_runner()
    monkeypatch.setattr(harvest_api, "_run_subprocess", runner)
    with pytest.raises(harvest_api.HarvestAlreadyRunningError):
        harvest_api.run_control_action("start")
    # subprocess must NOT have been invoked for a blocked start
    assert runner.calls == []


def test_stop_allowed_even_when_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harvest_api, "read_status_file", lambda: {"state": "running"})
    runner = _fake_runner()
    monkeypatch.setattr(harvest_api, "_run_subprocess", runner)
    result = harvest_api.run_control_action("stop")
    assert result["ok"] is True
    assert len(runner.calls) == 1


# ----------------------------------------------------------- read functions


def test_harvest_db_snapshot_missing_db(tmp_path: Path) -> None:
    snap = harvest_api.harvest_db_snapshot(tmp_path / "nope.db")
    assert snap["exists"] is False
    assert "detections_total" not in snap


def test_fetch_harvest_status_seeded(seeded: Path) -> None:
    status = harvest_api.fetch_harvest_status(seeded)
    assert status["detections_total"] == 1
    assert status["unique_advertisers"] == 1
    assert status["running"] is False  # no status file in test env
    assert status["db_path"] == str(seeded)


def test_status_exposes_db_path_identity(seeded: Path) -> None:
    """The JSON endpoint must surface the resolved DB path for verification."""
    status = harvest_api.fetch_harvest_status(seeded)
    assert status["db_path"] == str(seeded)
    assert status["exists"] is True


def test_harvest_warning_none_when_healthy(seeded: Path) -> None:
    status = harvest_api.fetch_harvest_status(seeded)
    assert harvest_api.harvest_warning(status) is None


def test_harvest_warning_when_zero_chunks(empty_db: Path) -> None:
    """A migrated-but-empty DB must surface a clear warning."""
    status = harvest_api.fetch_harvest_status(empty_db)
    assert status["chunks_created"] == 0
    warning = harvest_api.harvest_warning(status)
    assert warning is not None
    assert "0 chunks" in warning


def test_harvest_warning_when_db_missing(tmp_path: Path) -> None:
    status = harvest_api.fetch_harvest_status(tmp_path / "ghost.db")
    warning = harvest_api.harvest_warning(status)
    assert warning is not None
    assert "No pipeline database" in warning


def test_harvest_warning_when_chunks_but_no_detections(tmp_path: Path) -> None:
    """Stale DB with chunks but no detections must warn."""
    from shared.db import get_connection
    db = tmp_path / "stale.db"
    migrate(db)
    conn = get_connection(db)
    try:
        conn.execute(
            "INSERT INTO stations(name, url, format, enabled, display_name) "
            "VALUES ('test-am-1000', 'http://x', 'mp3', 1, 'Test')"
        )
        conn.execute(
            "INSERT INTO chunks(station_id, start_ts, end_ts, status, path) "
            "VALUES (1, 0, 1, 'done', '/x')"
        )
        conn.commit()
    finally:
        conn.close()
    status = harvest_api.fetch_harvest_status(db)
    assert status["chunks_created"] > 0
    assert status["detections_total"] == 0
    warning = harvest_api.harvest_warning(status)
    assert warning is not None
    assert "0 detections" in warning


def test_control_panel_shows_warning_on_empty_db(empty_db: Path) -> None:
    """The operator panel must show the DB warning banner when DB is empty."""
    client = TestClient(create_app(db_path=empty_db))
    resp = client.get("/radio-harvest")
    assert resp.status_code == 200
    assert "DB warning" in resp.text
    assert str(empty_db) in resp.text


def test_control_panel_no_warning_on_seeded_db(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    resp = client.get("/radio-harvest")
    assert resp.status_code == 200
    assert "DB warning" not in resp.text


def test_status_page_shows_db_path(seeded: Path) -> None:
    """The status page must display the resolved DB path."""
    client = TestClient(create_app(db_path=seeded))
    resp = client.get("/radio-harvest/status")
    assert resp.status_code == 200
    assert "db_path" in resp.text
    assert str(seeded) in resp.text


def test_fetch_harvest_detections_seeded(seeded: Path) -> None:
    rows = harvest_api.fetch_harvest_detections(seeded, limit=10)
    assert len(rows) == 1
    assert rows[0]["company_name"] == "Acme Funding"
    assert "business funding" in (rows[0]["keywords"] or "")
    assert rows[0]["chunk_status"] in {"done", "pending"}


def test_fetch_station_config_has_enabled_note() -> None:
    stations = harvest_api.fetch_station_config()
    assert len(stations) > 0
    assert all("stream_url" in s and "enabled" in s for s in stations)


def test_fetch_queue_health_detail_seeded(seeded: Path) -> None:
    health = harvest_api.fetch_queue_health_detail(seeded)
    assert "pending" in health and "done" in health and "dropped" in health
    assert isinstance(health["per_station"], list)
    assert "log_error_counts" in health


# ----------------------------------------------------------- HTML routes


@pytest.mark.parametrize("route", HARVEST_GET_ROUTES)
def test_harvest_get_routes_200_empty(empty_db: Path, route: str) -> None:
    client = TestClient(create_app(db_path=empty_db))
    response = client.get(route)
    assert response.status_code == 200, route


@pytest.mark.parametrize("route", HARVEST_GET_ROUTES)
def test_harvest_get_routes_200_seeded(seeded: Path, route: str) -> None:
    client = TestClient(create_app(db_path=seeded))
    response = client.get(route)
    assert response.status_code == 200, route


def test_control_panel_renders_buttons(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    html = client.get("/radio-harvest").text
    assert "Radio Harvest Control" in html
    assert "Probe Stations" in html
    assert "Start Overnight Harvest" in html
    assert "Stop Harvest" in html
    # nav link present
    assert 'href="/radio-harvest"' in html


def test_start_button_disabled_when_running(seeded: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harvest_api, "read_status_file", lambda: {"state": "running", "profile": "overnight_keyword_harvest"})
    client = TestClient(create_app(db_path=seeded))
    html = client.get("/radio-harvest").text
    assert "Start Overnight Harvest" in html
    # the start button is disabled, stop is enabled
    start_btn = html.split("Start Overnight Harvest")[0].rsplit("<button", 1)[-1]
    assert "disabled" in start_btn


def test_stations_page_shows_scaling_note(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    html = client.get("/radio-harvest/stations").text
    assert "config/stations.yaml" in html
    assert "<th>station_id</th>" in html


def test_detections_page_shows_acme(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    html = client.get("/radio-harvest/detections").text
    assert "Acme Funding" in html


# ----------------------------------------------------------- POST actions


def test_post_probe_redirects_with_flash(seeded: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harvest_api, "read_status_file", lambda: {})
    monkeypatch.setattr(
        harvest_api, "_run_subprocess",
        _fake_runner(ok=True, stdout="9/9 reachable."),
    )
    client = TestClient(create_app(db_path=seeded))
    response = client.post("/radio-harvest/probe", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/radio-harvest?msg=probe_ok")
    # follow redirect renders the flash
    follow = client.get(response.headers["location"])
    assert "Probe finished" in follow.text


def test_post_start_blocked_when_running(seeded: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harvest_api, "read_status_file", lambda: {"state": "running"})
    runner = _fake_runner()
    monkeypatch.setattr(harvest_api, "_run_subprocess", runner)
    client = TestClient(create_app(db_path=seeded))
    response = client.post("/radio-harvest/start", follow_redirects=False)
    assert response.status_code == 303
    assert "already_running" in response.headers["location"]
    assert runner.calls == []  # no subprocess


# ----------------------------------------------------------- JSON endpoints


def test_json_status(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    data = client.get("/api/harvest/status").json()
    assert data["detections_total"] == 1
    assert data["running"] is False


def test_json_start_conflict_when_running(seeded: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harvest_api, "read_status_file", lambda: {"state": "running"})
    monkeypatch.setattr(harvest_api, "_run_subprocess", _fake_runner())
    client = TestClient(create_app(db_path=seeded))
    response = client.post("/api/harvest/start")
    assert response.status_code == 409
    assert "already" in response.json()["error"].lower()


def test_json_unknown_action_is_404_or_422(seeded: Path) -> None:
    """The action path is fixed in the router — arbitrary actions are not routed."""
    client = TestClient(create_app(db_path=seeded))
    # /api/harvest/<arbitrary> is not a registered route
    response = client.post("/api/harvest/rm-rf")
    assert response.status_code in {404, 405}


def test_json_detections_and_queue_and_stations(seeded: Path) -> None:
    client = TestClient(create_app(db_path=seeded))
    d = client.get("/api/harvest/detections").json()
    assert d["count"] == 1
    q = client.get("/api/harvest/queue-health").json()
    assert "pending" in q and "per_station" in q
    s = client.get("/api/harvest/stations").json()
    assert len(s["stations"]) > 0


# ------------------------------------------------------ read-only guarantee


def test_harvest_get_routes_never_open_writable(
    seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shared.db as shared_db

    original = shared_db.get_connection

    def strict_get_connection(path, *, read_only: bool = False):
        if not read_only:
            raise AssertionError("Harvest GET routes must use read_only=True")
        return original(path, read_only=read_only)

    monkeypatch.setattr(shared_db, "get_connection", strict_get_connection)
    monkeypatch.setattr(harvest_api, "get_connection", strict_get_connection)
    client = TestClient(create_app(db_path=seeded))
    for route in HARVEST_GET_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
