"""Tests for station watchdog tracer bullet."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from dashboard.main import create_app
from shared.config import load_settings
from shared.db import get_connection, migrate
from shared.models import WatchdogSettings
from shared.station_control import fetch_pending_commands
from watchdog.health import classify_station_health
from watchdog.repository import fetch_recent_recovery_events
from watchdog.station_watchdog import run_health_check


def _seed_stale_station(db_path: Path, *, now: float, name: str = "stale-station") -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES (?, 'http://x', 1)",
            (name,),
        )
        conn.execute(
            """
            INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
            VALUES (1, 'old.wav', ?, ?, 'done')
            """,
            (now - 900, now - 810),
        )
        conn.commit()
    finally:
        conn.close()


def test_migration_016_creates_watchdog_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    applied = migrate(db_path)
    assert 16 in applied
    conn = get_connection(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    finally:
        conn.close()
    assert "station_health" in tables
    assert "station_recovery_events" in tables


def test_classify_stale_station() -> None:
    settings = WatchdogSettings(station_stale_after_minutes=6)
    now = 1_700_000_000.0
    snap = classify_station_health(
        station_name="klif-am-570",
        enabled=True,
        last_chunk_ts=now - 8 * 60,
        now_ts=now,
        settings=settings,
    )
    assert snap.is_stale is True
    assert snap.health_state == "stale"


def test_classify_healthy_station() -> None:
    settings = WatchdogSettings(station_stale_after_minutes=6)
    now = 1_700_000_000.0
    snap = classify_station_health(
        station_name="klif-am-570",
        enabled=True,
        last_chunk_ts=now - 60,
        now_ts=now,
        settings=settings,
    )
    assert snap.is_stale is False
    assert snap.health_state == "healthy"


def test_run_health_check_logs_stale_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(
        station_stale_after_minutes=6,
        target_active_stations=10,
        auto_restart_on_stale=False,
    )
    summary = run_health_check(db_path, settings=settings)
    assert summary["counts"]["stale"] == 1
    assert summary["restarts_queued"] == 0
    events = fetch_recent_recovery_events(db_path, limit=5)
    assert events
    assert events[0]["event_type"] == "stale_detected"
    assert events[0]["station_id"] == "stale-station"


def test_auto_restart_queues_command_on_new_stale_episode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(
        station_stale_after_minutes=6,
        auto_restart_on_stale=True,
        restart_attempts_before_disable=3,
    )
    summary = run_health_check(db_path, settings=settings)
    assert summary["restarts_queued"] == 1
    assert summary["stations_disabled"] == 0

    pending = fetch_pending_commands(db_path)
    assert len(pending) == 1
    assert pending[0]["station_id"] == "stale-station"
    assert pending[0]["command"] == "restart_station"

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT health_state, restart_count_today FROM station_health WHERE station_id = ?",
            ("stale-station",),
        ).fetchone()
    finally:
        conn.close()
    assert row["health_state"] == "recovering"
    assert row["restart_count_today"] == 1

    event_types = {e["event_type"] for e in fetch_recent_recovery_events(db_path, limit=10)}
    assert "restart_attempted" in event_types


def test_auto_restart_disables_after_consecutive_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO station_health (
                station_id, health_state, enabled, consecutive_failures
            ) VALUES ('stale-station', 'stale', 1, 2)
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(
        station_stale_after_minutes=6,
        auto_restart_on_stale=True,
        restart_attempts_before_disable=3,
    )
    summary = run_health_check(db_path, settings=settings)
    assert summary["stations_disabled"] == 1
    assert summary["restarts_queued"] == 0
    pending = fetch_pending_commands(db_path)
    assert len(pending) == 1
    assert pending[0]["command"] == "disable_station"

    conn = get_connection(db_path)
    try:
        station = conn.execute(
            "SELECT enabled FROM stations WHERE name = 'stale-station'"
        ).fetchone()
        health = conn.execute(
            "SELECT health_state, enabled FROM station_health WHERE station_id = 'stale-station'"
        ).fetchone()
    finally:
        conn.close()
    assert station["enabled"] == 0
    assert health["health_state"] == "failed"
    assert health["enabled"] == 0


def test_auto_restart_skips_during_cooldown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO station_health (
                station_id, health_state, enabled, cool_down_until
            ) VALUES ('stale-station', 'failed', 1, ?)
            """,
            (datetime.fromtimestamp(now + 3600, tz=UTC).isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=True)
    summary = run_health_check(db_path, settings=settings)
    assert summary["restarts_queued"] == 0
    assert fetch_pending_commands(db_path) == []


def test_healthy_station_resets_consecutive_failures(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('ok-station', 'http://x', 1)"
        )
        conn.execute(
            """
            INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
            VALUES (1, 'fresh.wav', ?, ?, 'done')
            """,
            (now - 30, now - 10),
        )
        conn.execute(
            """
            INSERT INTO station_health (
                station_id, health_state, enabled, consecutive_failures
            ) VALUES ('ok-station', 'stale', 1, 4)
            """
        )
        conn.commit()
    finally:
        conn.close()

    run_health_check(
        db_path,
        settings=WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=False),
    )

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT health_state, consecutive_failures FROM station_health WHERE station_id = ?",
            ("ok-station",),
        ).fetchone()
    finally:
        conn.close()
    assert row["health_state"] == "healthy"
    assert row["consecutive_failures"] == 0


def test_watchdog_settings_load_from_yaml() -> None:
    settings = load_settings()
    assert settings.watchdog.enabled is True
    assert settings.watchdog.target_active_stations == 10
    assert settings.watchdog.station_stale_after_minutes == 6
    assert settings.watchdog.auto_restart_on_stale is True


def test_ops_watchdog_route(tmp_path: Path) -> None:
    db_path = tmp_path / "dash.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('a-station', 'http://a', 1)"
        )
        conn.execute(
            """
            INSERT INTO station_health (station_id, health_state, enabled)
            VALUES ('a-station', 'healthy', 1)
            """
        )
        conn.commit()
    finally:
        conn.close()

    client = TestClient(create_app(db_path=db_path))
    response = client.get("/ops/watchdog")
    assert response.status_code == 200
    assert b"Station Watchdog" in response.content
    assert b"a-station" in response.content
