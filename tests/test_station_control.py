"""Tests for station control commands and ingestor polling."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi.testclient import TestClient

from dashboard.main import create_app
from ingestor.control import IngestorControlContext, process_pending_commands
from ingestor.supervisor import BackoffPolicy, StationIngestor
from shared.db import get_connection, migrate
from shared.models import PipelineSettings, StationConfig
from shared.station_control import (
    CommandStatus,
    StationControlCommand,
    enqueue_station_command,
    fetch_pending_commands,
)
from tests.test_ingestor import FakeClock, FakeRunner


def test_migration_017_creates_control_commands(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    applied = migrate(db_path)
    assert 17 in applied
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='station_control_commands'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_enqueue_and_fetch_pending_command(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('klif-am-570', 'http://x', 1)"
        )
        conn.commit()
    finally:
        conn.close()

    command_id = enqueue_station_command(
        db_path,
        station_id="klif-am-570",
        command=StationControlCommand.RESTART,
        reason="test",
    )
    pending = fetch_pending_commands(db_path)
    assert len(pending) == 1
    assert pending[0]["id"] == command_id
    assert pending[0]["command"] == "restart_station"
    assert pending[0]["status"] == CommandStatus.PENDING.value


def test_process_restart_command_marks_done_and_logs_event(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    station = StationConfig(name="klif-am-570", url="http://x", enabled=True)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
            (station.name, station.url),
        )
        conn.commit()
    finally:
        conn.close()

    settings = PipelineSettings(chunk_len=90, overlap=7, ingest_immediate_retries=0)
    clock = FakeClock(start=100.0)
    runner = FakeRunner(returncode=1, write_file=False)
    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=30, max_seconds=30),
    )
    ingestors = {station.name: ingestor}

    enqueue_station_command(
        db_path,
        station_id=station.name,
        command=StationControlCommand.RESTART,
        reason="unit test",
    )

    handled = process_pending_commands(db_path, ingestors)
    assert handled == 1
    assert fetch_pending_commands(db_path) == []
    assert ingestor.restart_event.is_set() is False
    assert ingestor.backoff.current_seconds is None

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM station_control_commands ORDER BY id DESC LIMIT 1"
        ).fetchone()
        event = conn.execute(
            "SELECT event_type, action_taken FROM station_recovery_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["status"] == CommandStatus.DONE.value
    assert event["event_type"] == "restart_requested"
    assert event["action_taken"] == "restart_station"


def test_process_disable_command_stops_ingestor(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    station = StationConfig(name="klif-am-570", url="http://x", enabled=True)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
            (station.name, station.url),
        )
        conn.commit()
    finally:
        conn.close()

    settings = PipelineSettings(chunk_len=90, overlap=7, ingest_immediate_retries=0)
    clock = FakeClock(start=100.0)
    runner = FakeRunner(returncode=1, write_file=False)
    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=30, max_seconds=30),
    )
    ingestors = {station.name: ingestor}

    enqueue_station_command(
        db_path,
        station_id=station.name,
        command=StationControlCommand.DISABLE,
        reason="unit test",
    )

    handled = process_pending_commands(db_path, ingestors)
    assert handled == 1
    assert ingestors == {}
    assert ingestor.stop_event.is_set() is True
    assert fetch_pending_commands(db_path) == []

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM station_control_commands ORDER BY id DESC LIMIT 1"
        ).fetchone()
        event = conn.execute(
            "SELECT event_type, action_taken FROM station_recovery_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["status"] == CommandStatus.DONE.value
    assert event["event_type"] == "station_stopped"
    assert event["action_taken"] == "disable_station"


def test_process_promote_command_starts_ingestor(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)
    station = StationConfig(name="backup-b", url="http://b", enabled=True)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
            (station.name, station.url),
        )
        conn.commit()
    finally:
        conn.close()

    settings = PipelineSettings(chunk_len=90, overlap=7, ingest_immediate_retries=0)
    ingestors: dict[str, StationIngestor] = {}
    threads: dict[str, threading.Thread] = {}
    stop_event = threading.Event()
    context = IngestorControlContext(
        db_path=db_path,
        settings=settings,
        chunks_dir=tmp_path / "chunks",
        threads=threads,
        stop_event=stop_event,
    )

    enqueue_station_command(
        db_path,
        station_id=station.name,
        command=StationControlCommand.PROMOTE,
        reason="unit test",
    )

    handled = process_pending_commands(db_path, ingestors, context=context)
    assert handled == 1
    assert station.name in ingestors
    assert station.name in threads
    assert threads[station.name].is_alive()

    stop_event.set()
    threads[station.name].join(timeout=2.0)


def test_request_restart_resets_backoff(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Backoff FM", url="https://example.com/live", enabled=True)
    settings = PipelineSettings(chunk_len=90, overlap=7)
    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=FakeRunner(returncode=1, write_file=False),
        clock=FakeClock(start=1_000.0),
        backoff=BackoffPolicy(initial_seconds=30, max_seconds=30),
    )
    ingestor.backoff.next_delay()
    ingestor.request_restart()
    ingestor._apply_restart()
    assert ingestor.backoff.current_seconds is None
    assert ingestor.restart_event.is_set() is False


def test_dashboard_restart_posts_command(tmp_path: Path) -> None:
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
            VALUES ('a-station', 'stale', 1)
            """
        )
        conn.commit()
    finally:
        conn.close()

    client = TestClient(create_app(db_path=db_path))
    response = client.post("/ops/watchdog/restart/a-station", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/ops/watchdog?restarted=a-station"

    pending = fetch_pending_commands(db_path)
    assert len(pending) == 1
    assert pending[0]["station_id"] == "a-station"
