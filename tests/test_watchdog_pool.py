"""Tests for replacement pool sync, selection, and queue-gated promotion."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from shared.db import get_connection, migrate
from shared.models import StationConfig, StationPoolMeta, WatchdogSettings
from shared.station_control import CommandStatus, fetch_pending_commands
from watchdog.pool import (
    count_pool_available,
    select_backup_candidate,
    sync_station_pool,
)
from watchdog.promotion import maybe_promote_backup
from watchdog.repository import fetch_recent_recovery_events
from watchdog.station_watchdog import run_health_check


def test_migration_018_creates_station_pool(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    applied = migrate(db_path)
    assert 18 in applied
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='station_pool'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_sync_station_pool_requires_explicit_replacement_opt_in(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    stations = [
        StationConfig(name="active-a", url="http://active", enabled=True),
        StationConfig(name="backup-b", url="http://backup", enabled=False),
    ]
    sync_station_pool(db_path, stations)

    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://active', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://backup', 0)"
        )
        conn.commit()
        active = conn.execute(
            "SELECT replacement_eligible FROM station_pool WHERE station_id = 'active-a'"
        ).fetchone()
        backup = conn.execute(
            "SELECT replacement_eligible, priority FROM station_pool WHERE station_id = 'backup-b'"
        ).fetchone()
    finally:
        conn.close()
    assert active["replacement_eligible"] == 0
    assert backup["replacement_eligible"] == 0
    assert backup["priority"] == 100


def test_sync_station_pool_preserves_pool_lock_in_fixed_harvest_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 0, 100, 'OLD')
            """
        )
        conn.commit()
    finally:
        conn.close()

    sync_station_pool(
        db_path,
        [
            StationConfig(
                name="backup-b",
                url="http://backup",
                enabled=False,
                pool=StationPoolMeta(replacement_eligible=True, priority=10, market="DFW"),
            )
        ],
        settings=WatchdogSettings(fixed_harvest_mode=True),
    )

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT replacement_eligible, priority, market
            FROM station_pool
            WHERE station_id = 'backup-b'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row["replacement_eligible"] == 0
    assert row["priority"] == 10
    assert row["market"] == "DFW"


def test_select_backup_candidate_honors_priority_and_duplicate_url(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    stations = [
        StationConfig(
            name="active-a",
            url="http://shared",
            enabled=True,
            pool=StationPoolMeta(replacement_eligible=False, market="DFW"),
        ),
        StationConfig(
            name="backup-low",
            url="http://shared",
            enabled=False,
            pool=StationPoolMeta(replacement_eligible=True, priority=50, market="DFW"),
        ),
        StationConfig(
            name="backup-high",
            url="http://unique",
            enabled=False,
            pool=StationPoolMeta(replacement_eligible=True, priority=10, market="HOU"),
        ),
    ]
    sync_station_pool(db_path, stations)
    conn = get_connection(db_path)
    try:
        for station in stations:
            conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES (?, ?, ?)",
                (station.name, station.url, 1 if station.enabled else 0),
            )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(max_active_per_market=2)
    candidate = select_backup_candidate(db_path, settings=settings, now_ts=time.time())
    assert candidate is not None
    assert candidate["station_id"] == "backup-high"


def test_promotion_blocked_when_queue_critical(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://a', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 1, 10, 'HOU')
            """
        )
        for _ in range(10):
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (1, 'd.wav', 1, 2, 'dropped')
                """
            )
        conn.execute(
            """
            INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
            VALUES (1, 'ok.wav', 3, 4, 'done')
            """
        )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(
        target_active_stations=2,
        queue_drop_ratio_critical=5.0,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=True,
    )
    from watchdog.station_watchdog import queue_snapshot

    queue = queue_snapshot(db_path, settings)
    assert queue.level == "critical"
    result = maybe_promote_backup(db_path, settings=settings, queue=queue)
    assert result == "promotion_blocked_queue"
    assert fetch_pending_commands(db_path) == []


def test_replacement_eligible_zero_blocks_promotion(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://a', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 0, 10, 'HOU')
            """
        )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(
        target_active_stations=2,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=True,
    )
    from watchdog.notify import QueueSnapshot

    queue = QueueSnapshot(done=10, dropped=1, pending=0, drop_ratio=0.1, level="ok")
    result = maybe_promote_backup(db_path, settings=settings, queue=queue)
    assert result == "pool_empty"
    assert fetch_pending_commands(db_path) == []

    conn = get_connection(db_path)
    try:
        enabled = conn.execute(
            "SELECT enabled FROM stations WHERE name = 'backup-b'"
        ).fetchone()["enabled"]
    finally:
        conn.close()
    assert enabled == 0


def test_fixed_harvest_blocks_promote_station(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('klif-am-570', 'http://k', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 1, 10, 'HOU')
            """
        )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(
        fixed_harvest_mode=True,
        fixed_harvest_station_ids=["klif-am-570", "wbap-am-820"],
        target_active_stations=2,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=True,
    )
    from watchdog.notify import QueueSnapshot

    queue = QueueSnapshot(done=10, dropped=1, pending=0, drop_ratio=0.1, level="ok")
    result = maybe_promote_backup(db_path, settings=settings, queue=queue)
    assert result == "promotion_blocked_fixed_harvest"
    assert fetch_pending_commands(db_path) == []

    conn = get_connection(db_path)
    try:
        enabled = conn.execute(
            "SELECT enabled FROM stations WHERE name = 'backup-b'"
        ).fetchone()["enabled"]
    finally:
        conn.close()
    assert enabled == 0


def test_auto_promotion_requires_explicit_enable_flag(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://a', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 1, 10, 'HOU')
            """
        )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(
        target_active_stations=2,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=False,
    )
    from watchdog.notify import QueueSnapshot

    queue = QueueSnapshot(done=10, dropped=1, pending=0, drop_ratio=0.1, level="ok")
    result = maybe_promote_backup(db_path, settings=settings, queue=queue)
    assert result is None
    assert fetch_pending_commands(db_path) == []


def test_promotion_enqueues_command_when_active_below_target(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://a', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 1, 10, 'HOU')
            """
        )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(
        target_active_stations=2,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=True,
    )
    from watchdog.notify import QueueSnapshot

    queue = QueueSnapshot(done=10, dropped=1, pending=0, drop_ratio=0.1, level="ok")
    result = maybe_promote_backup(db_path, settings=settings, queue=queue)
    assert result == "promoted"

    conn = get_connection(db_path)
    try:
        enabled = conn.execute(
            "SELECT enabled FROM stations WHERE name = 'backup-b'"
        ).fetchone()
    finally:
        conn.close()
    assert enabled["enabled"] == 1

    pending = fetch_pending_commands(db_path)
    assert len(pending) == 1
    assert pending[0]["command"] == "promote_station"
    events = fetch_recent_recovery_events(db_path, limit=5)
    assert events[0]["event_type"] == "station_promoted"


def test_pending_command_prevents_duplicate_promotion(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://a', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 1, 10, 'HOU')
            """
        )
        conn.execute(
            """
            INSERT INTO station_control_commands (
                station_id, command, status, reason
            ) VALUES ('backup-b', 'restart_station', ?, 'manual work in progress')
            """,
            (CommandStatus.PROCESSING.value,),
        )
        conn.commit()
    finally:
        conn.close()

    settings = WatchdogSettings(
        target_active_stations=2,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=True,
    )
    from watchdog.notify import QueueSnapshot

    queue = QueueSnapshot(done=10, dropped=1, pending=0, drop_ratio=0.1, level="ok")
    result = maybe_promote_backup(db_path, settings=settings, queue=queue)
    assert result == "promotion_pending"

    conn = get_connection(db_path)
    try:
        enabled = conn.execute(
            "SELECT enabled FROM stations WHERE name = 'backup-b'"
        ).fetchone()["enabled"]
        commands = conn.execute(
            "SELECT status, COUNT(*) AS n FROM station_control_commands GROUP BY status"
        ).fetchall()
    finally:
        conn.close()

    assert enabled == 0
    assert [(row["status"], row["n"]) for row in commands] == [
        (CommandStatus.PROCESSING.value, 1)
    ]


def test_run_health_check_reports_promotion_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('active-a', 'http://a', 1)"
        )
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('backup-b', 'http://b', 0)"
        )
        conn.execute(
            """
            INSERT INTO station_pool (
                station_id, replacement_eligible, priority, market
            ) VALUES ('backup-b', 1, 10, 'HOU')
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr("watchdog.station_watchdog.send_stale_station_alert", lambda *a, **k: False)

    settings = WatchdogSettings(
        target_active_stations=2,
        promote_backup_when_active_below_target=True,
        auto_promotion_enabled=True,
        auto_restart_on_stale=False,
    )
    summary = run_health_check(db_path, settings=settings)
    assert summary["promotion_action"] == "promoted"
    assert summary["pool_available"] >= 1
