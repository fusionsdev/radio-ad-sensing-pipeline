"""Tests for chunk file janitor — retention and RAM-disk cleanup."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from shared.db import get_connection, migrate, transaction
from shared.models import ChunkStatus, PipelineSettings
from worker.janitor import ChunkJanitor, delete_chunk_file


def _seed_station(conn: sqlite3.Connection, *, name: str = "news-talk") -> int:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
        (name, "https://example.com/live"),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_chunk(
    conn: sqlite3.Connection,
    *,
    station_id: int,
    path: str,
    start_ts: float,
    end_ts: float,
    status: str = ChunkStatus.PENDING.value,
) -> int:
    conn.execute(
        """
        INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (station_id, path, start_ts, end_ts, status),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "pipeline.db"
    migrate(path)
    return path


@pytest.fixture
def settings(tmp_path: Path) -> PipelineSettings:
    return PipelineSettings(
        chunks_dir=str(tmp_path / "chunks"),
        retention_hours=48,
    )


def test_delete_chunk_file_removes_wav_and_is_idempotent(tmp_path: Path) -> None:
    wav = tmp_path / "chunk.wav"
    wav.write_bytes(b"RIFF")

    assert delete_chunk_file(wav) is True
    assert not wav.exists()
    assert delete_chunk_file(wav) is False


def test_delete_after_processing_leaves_db_row(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    wav = chunks_dir / "station" / "1000.wav"
    wav.parent.mkdir(parents=True)
    wav.write_bytes(b"RIFF")

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _seed_chunk(
                conn,
                station_id=station_id,
                path=str(wav),
                start_ts=1000.0,
                end_ts=1090.0,
                status=ChunkStatus.DONE.value,
            )
    finally:
        conn.close()

    janitor = ChunkJanitor(db_path, settings, chunks_dir=chunks_dir)
    assert janitor.delete_after_processing(wav) is True
    assert not wav.exists()

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT id FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_expire_stale_pending_marks_dropped_logs_gap_and_deletes_file(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    wav = chunks_dir / "stale.wav"
    wav.write_bytes(b"RIFF")

    now = 2_000_000.0
    stale_start = now - (settings.retention_hours * 3600) - 60.0

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(wav),
                start_ts=stale_start,
                end_ts=stale_start + 90.0,
            )
    finally:
        conn.close()

    janitor = ChunkJanitor(db_path, settings, chunks_dir=chunks_dir, now_fn=lambda: now)
    expired = janitor.expire_stale_pending()
    assert expired == 1
    assert not wav.exists()

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT status, error FROM chunks WHERE path = ?",
            (str(wav),),
        ).fetchone()
        assert row["status"] == ChunkStatus.DROPPED.value
        assert row["error"] == "retention_expired"

        gap = conn.execute(
            "SELECT reason FROM gaps WHERE station_id = ?",
            (station_id,),
        ).fetchone()
        assert gap["reason"] == "retention_expired"
    finally:
        conn.close()


def test_sweep_orphans_removes_untracked_files(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    chunks_dir = tmp_path / "chunks"
    orphan = chunks_dir / "orphan" / "999.wav"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"RIFF")

    janitor = ChunkJanitor(db_path, settings, chunks_dir=chunks_dir)
    removed = janitor.sweep_orphans()
    assert removed == 1
    assert not orphan.exists()


def test_janitor_never_deletes_ad_archive_files(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    archive_dir = tmp_path / "ad_archive"
    archive_dir.mkdir()
    archived = archive_dir / "canonical_ad_1.wav"
    archived.write_bytes(b"RIFF")

    janitor = ChunkJanitor(
        db_path,
        settings,
        chunks_dir=tmp_path / "chunks",
        archive_dir=archive_dir,
    )
    assert janitor.delete_after_processing(archived) is False
    assert archived.exists()


def test_cleanup_dropped_files_removes_wav(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    wav = chunks_dir / "dropped.wav"
    wav.write_bytes(b"RIFF")

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(wav),
                start_ts=time.time(),
                end_ts=time.time() + 90.0,
                status=ChunkStatus.DROPPED.value,
            )
    finally:
        conn.close()

    janitor = ChunkJanitor(db_path, settings, chunks_dir=chunks_dir)
    removed = janitor.cleanup_dropped_files()
    assert removed == 1
    assert not wav.exists()


def test_run_sweep_runs_passive_wal_checkpoint(
    db_path: Path,
    settings: PipelineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_checkpoint(path: Path, *, mode: str = "PASSIVE"):
        calls.append(mode)
        from shared.db import WalCheckpointResult

        return WalCheckpointResult(busy=False, log_frames=3, checkpointed_frames=2)

    monkeypatch.setattr("worker.janitor.checkpoint_wal", fake_checkpoint)
    metrics: list[tuple[int, int, int]] = []

    def fake_metrics(result) -> None:
        metrics.append((result.log_frames, result.checkpointed_frames, int(result.busy)))

    monkeypatch.setattr("worker.janitor.set_wal_checkpoint_metrics", fake_metrics)

    janitor = ChunkJanitor(db_path, settings)
    summary = janitor.run_sweep()

    assert calls == ["PASSIVE"]
    assert summary["wal_checkpointed_frames"] == 2
    assert metrics == [(3, 2, 0)]


def test_passive_wal_checkpoint_continues_on_failure(
    db_path: Path,
    settings: PipelineSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_path, *, mode: str = "PASSIVE"):
        raise sqlite3.OperationalError("checkpoint failed")

    monkeypatch.setattr("worker.janitor.checkpoint_wal", boom)

    janitor = ChunkJanitor(db_path, settings)
    assert janitor.passive_wal_checkpoint() == 0
    assert janitor.run_sweep()["wal_checkpointed_frames"] == 0
