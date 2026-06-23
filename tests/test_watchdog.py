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
from shared.station_control import CommandStatus, StationControlCommand, fetch_pending_commands
from watchdog.health import classify_station_health
from watchdog.repository import fetch_recent_recovery_events
from watchdog.recovery import auto_restart_stale_station
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


def test_healthy_station_clears_recovery_state(tmp_path: Path) -> None:
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
                station_id, health_state, enabled, consecutive_failures,
                restart_count_today, cool_down_until, last_error
            ) VALUES ('ok-station', 'recovering', 1, 3, 2, ?, 'daily restart limit (5) reached')
            """,
            (datetime.fromtimestamp(now + 3600, tz=UTC).isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO status (key, value, updated_at)
            VALUES ('watchdog:restart_attempt:ok-station', 'old', ?)
            """,
            (now,),
        )
        conn.commit()
    finally:
        conn.close()

    run_health_check(
        db_path,
        settings=WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=True),
    )

    conn = get_connection(db_path)
    try:
        health = conn.execute(
            """
            SELECT health_state, consecutive_failures, restart_count_today,
                   cool_down_until, last_error
            FROM station_health
            WHERE station_id = 'ok-station'
            """
        ).fetchone()
        restart_marker = conn.execute(
            "SELECT value FROM status WHERE key = 'watchdog:restart_attempt:ok-station'"
        ).fetchone()
        commands = conn.execute("SELECT COUNT(*) AS n FROM station_control_commands").fetchone()
    finally:
        conn.close()

    assert health["health_state"] == "healthy"
    assert health["consecutive_failures"] == 0
    assert health["restart_count_today"] == 0
    assert health["cool_down_until"] is None
    assert health["last_error"] is None
    assert restart_marker is None
    assert commands["n"] == 0


def test_watchdog_does_not_restart_with_processing_command(
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
            INSERT INTO station_control_commands (
                station_id, command, status, reason
            ) VALUES ('stale-station', 'restart_station', 'processing', 'already running')
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    summary = run_health_check(
        db_path,
        settings=WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=True),
    )

    conn = get_connection(db_path)
    try:
        commands = conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM station_control_commands
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()
    finally:
        conn.close()

    assert summary["restarts_queued"] == 0
    assert [(row["status"], row["n"]) for row in commands] == [
        (CommandStatus.PROCESSING.value, 1)
    ]


def test_watchdog_respects_recent_manual_enable_grace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)
    processed_at = datetime.fromtimestamp(now - 5 * 60, tz=UTC).isoformat()
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO station_control_commands (
                station_id, command, status, reason, processed_at
            ) VALUES ('stale-station', 'enable_station', 'done', 'manual resume', ?)
            """,
            (processed_at,),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(
        station_stale_after_minutes=6,
        manual_recovery_grace_minutes=20,
        auto_restart_on_stale=True,
    )
    summary = run_health_check(db_path, settings=settings)

    pending = fetch_pending_commands(db_path)
    assert summary["restarts_queued"] == 0
    assert pending == []


def test_auto_restart_skips_when_db_has_fresher_chunk_than_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
            VALUES (1, 'fresh.wav', ?, ?, 'done')
            """,
            (now - 30, now - 10),
        )
        conn.commit()
    finally:
        conn.close()

    snap = classify_station_health(
        station_name="stale-station",
        enabled=True,
        last_chunk_ts=now - 900,
        now_ts=now,
        settings=WatchdogSettings(station_stale_after_minutes=6),
    )
    action = auto_restart_stale_station(
        db_path,
        snap,
        settings=WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=True),
        now_ts=now,
    )

    assert action == "fresh_skip"
    assert fetch_pending_commands(db_path) == []


def test_watchdog_recovery_is_idempotent_per_stale_outage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    _seed_stale_station(db_path, now=now)

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=True)
    first = run_health_check(db_path, settings=settings)
    second = run_health_check(db_path, settings=settings)

    conn = get_connection(db_path)
    try:
        restart_count = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM station_control_commands
            WHERE command = 'restart_station'
            """
        ).fetchone()["n"]
    finally:
        conn.close()

    assert first["restarts_queued"] == 1
    assert second["restarts_queued"] == 0
    assert restart_count == 1


def test_healthy_station_is_not_restarted_while_peer_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    now = time.time()
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('klif-am-570', 'http://k', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('wbap-am-820', 'http://w', 1)"
        )
        conn.execute(
            """
            INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
            VALUES (1, 'old.wav', ?, ?, 'done')
            """,
            (now - 900, now - 810),
        )
        conn.execute(
            """
            INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
            VALUES (2, 'fresh.wav', ?, ?, 'done')
            """,
            (now - 30, now - 10),
        )
        conn.execute(
            """
            INSERT INTO station_health (station_id, health_state, enabled)
            VALUES ('wbap-am-820', 'stale', 1)
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    summary = run_health_check(
        db_path,
        settings=WatchdogSettings(station_stale_after_minutes=6, auto_restart_on_stale=True),
    )

    conn = get_connection(db_path)
    try:
        wbap_commands = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM station_control_commands
            WHERE station_id = 'wbap-am-820'
            """
        ).fetchone()["n"]
        wbap_health = conn.execute(
            """
            SELECT health_state
            FROM station_health
            WHERE station_id = 'wbap-am-820'
            """
        ).fetchone()["health_state"]
    finally:
        conn.close()

    assert summary["restarts_queued"] == 1
    assert wbap_commands == 0
    assert wbap_health == "healthy"


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
