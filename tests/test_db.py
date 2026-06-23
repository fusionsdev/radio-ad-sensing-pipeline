"""Tests for SQLite migrations, connections, and SQLITE_BUSY retry."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from shared.db import (
    EXPECTED_TABLES,
    WalCheckpointResult,
    checkpoint_wal,
    get_connection,
    list_tables,
    migrate,
    retry_on_busy,
    transaction,
)


def test_migrate_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    applied = migrate(db_path)

    assert applied == [1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21, 22]
    tables = list_tables(db_path)
    for table in EXPECTED_TABLES:
        assert table in tables


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    first = migrate(db_path)
    second = migrate(db_path)

    assert first == [1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21, 22]
    assert second == []


def test_wal_and_busy_timeout(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)

    conn = get_connection(db_path)
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert journal_mode == "wal"
        assert busy_timeout == 5000
    finally:
        conn.close()


def test_read_only_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)

    conn = get_connection(db_path, read_only=True)
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert journal_mode == "wal"
        assert busy_timeout == 5000
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO stations (name, url) VALUES ('x', 'y')")
    finally:
        conn.close()


def test_checkpoint_wal_returns_result(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)

    writer = get_connection(db_path)
    try:
        writer.execute(
            "INSERT INTO stations (name, url, enabled) VALUES ('a', 'https://a', 1)"
        )
        writer.commit()
    finally:
        writer.close()

    result = checkpoint_wal(db_path, mode="PASSIVE")
    assert isinstance(result, WalCheckpointResult)
    assert isinstance(result.busy, bool)
    assert result.log_frames >= 0
    assert result.checkpointed_frames >= 0


def test_retry_on_busy_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    @retry_on_busy(max_retries=3, base_delay=0.001)
    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    assert flaky() == "ok"
    assert attempts["count"] == 3


def test_retry_on_busy_reraises_non_busy_errors() -> None:
    @retry_on_busy()
    def broken() -> None:
        raise sqlite3.OperationalError("no such table: missing")

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        broken()


def test_concurrent_writes_retry_on_sqlite_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "concurrent.db"
    migrate(db_path)

    errors: list[Exception] = []
    attempts = {"count": 0}
    release_retry = threading.Event()
    saw_busy = threading.Event()
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        saw_busy.set()
        assert release_retry.wait(timeout=5)

    monkeypatch.setattr("shared.db.time.sleep", fake_sleep)

    @retry_on_busy(max_retries=10, base_delay=0.005)
    def insert_station(name: str) -> None:
        attempts["count"] += 1
        conn = sqlite3.connect(db_path, timeout=0.0, check_same_thread=False)
        try:
            with transaction(conn):
                conn.execute(
                    "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
                    (name, f"https://example.com/{name}"),
                )
        finally:
            conn.close()

    def run_worker(name: str) -> None:
        try:
            insert_station(name)
        except Exception as exc:  # pragma: no cover - collected for assertion
            errors.append(exc)

    thread = threading.Thread(target=run_worker, args=("station-a",))

    locker = get_connection(db_path)
    try:
        locker.execute("BEGIN IMMEDIATE")
        thread.start()
        assert saw_busy.wait(timeout=5)
        locker.commit()
    finally:
        release_retry.set()
        locker.close()
    thread.join(timeout=10)

    follow_up = threading.Thread(target=run_worker, args=("station-b",))
    follow_up.start()
    follow_up.join(timeout=10)

    assert not errors
    assert sleep_calls
    assert sleep_calls[0] == pytest.approx(0.005)
    assert attempts["count"] >= 2

    conn = get_connection(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
        assert count == 2
    finally:
        conn.close()
