"""Tests for ASR worker consumer — no GPU; WhisperModel mocked."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from shared.db import get_connection, migrate, transaction
from shared.models import AdExtraction, ChunkStatus, PipelineSettings
from worker.consumer import ChunkConsumer
from worker.fingerprint import FingerprintMatch
from worker.transcribe import TranscriptSegment, TranscriptionResult


class FakeTranscriber:
    """Injected backend for tests."""

    def __init__(
        self,
        *,
        text: str = "hello world",
        wall_time_sec: float = 9.0,
        fail_on: set[Path] | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.text = text
        self.wall_time_sec = wall_time_sec
        self.fail_on = fail_on or set()
        self.fail_with = fail_with or RuntimeError("transcription failed")
        self.calls: list[Path] = []

    def transcribe(
        self,
        audio_path: Path,
        *,
        audio_duration_sec: float | None = None,
    ) -> TranscriptionResult:
        self.calls.append(audio_path)
        if audio_path in self.fail_on:
            raise self.fail_with
        duration = audio_duration_sec or 90.0
        return TranscriptionResult(
            text=self.text,
            segments=[
                TranscriptSegment(0.0, 1.0, "hello"),
                TranscriptSegment(1.0, 2.0, "world"),
            ],
            audio_duration_sec=duration,
            wall_time_sec=self.wall_time_sec,
        )


class FakeExtractor:
    def __init__(
        self,
        extraction: AdExtraction | None = None,
        *,
        fail_with: Exception | None = None,
    ) -> None:
        self.extraction = extraction
        self.fail_with = fail_with
        self.calls: list[str] = []

    def extract(self, transcript_text: str) -> AdExtraction:
        self.calls.append(transcript_text)
        if self.fail_with is not None:
            raise self.fail_with
        assert self.extraction is not None
        return self.extraction


class FakeDetectionPersister:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_extraction(
        self,
        chunk_id: int,
        extraction: AdExtraction,
        *,
        transcript_text: str,
        segments: list[TranscriptSegment],
    ) -> int | None:
        self.calls.append(
            {
                "chunk_id": chunk_id,
                "extraction": extraction,
                "transcript_text": transcript_text,
                "segments": segments,
            }
        )
        return 123


class FakeFingerprintAnnotator:
    def __init__(self, match: FingerprintMatch | None) -> None:
        self.match = match
        self.calls: list[tuple[int, Path]] = []

    def annotate_chunk(self, chunk_id: int, audio_path: Path) -> FingerprintMatch | None:
        self.calls.append((chunk_id, audio_path))
        return self.match


def _seed_station(conn: sqlite3.Connection, name: str = "test-fm") -> int:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
        (name, "https://example.com/stream"),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_chunk(
    conn: sqlite3.Connection,
    *,
    station_id: int,
    path: str,
    start_ts: float,
    end_ts: float,
    status: str = "pending",
) -> int:
    conn.execute(
        """
        INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (station_id, path, start_ts, end_ts, status),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


@pytest.fixture
def worker_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "worker.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def settings() -> PipelineSettings:
    return PipelineSettings(queue_max_hours=2, chunk_len=90)


def test_consumer_claim_transcript_and_done(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "chunk.wav"
    audio.write_bytes(b"fake wav")

    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            _insert_chunk(
                conn,
                station_id=station_id,
                path=str(audio),
                start_ts=1000.0,
                end_ts=1090.0,
            )
    finally:
        conn.close()

    transcriber = FakeTranscriber(wall_time_sec=9.0)
    consumer = ChunkConsumer(worker_db, settings, transcriber)

    assert consumer.run_once() is True

    conn = get_connection(worker_db)
    try:
        chunk = conn.execute("SELECT status, error FROM chunks").fetchone()
        assert chunk["status"] == ChunkStatus.DONE.value
        assert chunk["error"] is None

        transcript = conn.execute(
            "SELECT text, asr_duration_ms, segments_json FROM transcripts"
        ).fetchone()
        assert transcript["text"] == "hello world"
        assert transcript["asr_duration_ms"] == 9000
        segments = json.loads(transcript["segments_json"])
        assert len(segments) == 2
        assert segments[0]["start"] == 0.0

        rtf_avg = conn.execute(
            "SELECT value FROM status WHERE key = 'asr_rtf_avg'"
        ).fetchone()
        assert rtf_avg is not None
        assert abs(float(rtf_avg["value"]) - 0.1) < 0.001
    finally:
        conn.close()


def test_consumer_runs_extraction_and_dedup_after_transcription(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "chunk.wav"
    audio.write_bytes(b"fake wav")

    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _insert_chunk(
                conn,
                station_id=station_id,
                path=str(audio),
                start_ts=1000.0,
                end_ts=1090.0,
            )
    finally:
        conn.close()

    extraction = AdExtraction(is_ad=True, company_name="Rapid Capital", confidence=0.9)
    extractor = FakeExtractor(extraction)
    persister = FakeDetectionPersister()
    transcriber = FakeTranscriber(text="Rapid Capital funding ad", wall_time_sec=3.0)
    consumer = ChunkConsumer(
        worker_db,
        settings,
        transcriber,
        extractor=extractor,
        detection_persister=persister,
    )

    assert consumer.run_once() is True

    assert extractor.calls == ["Rapid Capital funding ad"]
    assert len(persister.calls) == 1
    assert persister.calls[0]["chunk_id"] == chunk_id
    assert persister.calls[0]["extraction"] == extraction
    assert persister.calls[0]["transcript_text"] == "Rapid Capital funding ad"
    assert len(persister.calls[0]["segments"]) == 2


def test_consumer_skips_llm_extraction_when_fingerprint_marks_known_ad(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "known.wav"
    audio.write_bytes(b"fake wav")

    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _insert_chunk(
                conn,
                station_id=station_id,
                path=str(audio),
                start_ts=1000.0,
                end_ts=1090.0,
            )
    finally:
        conn.close()

    extractor = FakeExtractor(AdExtraction(is_ad=True, company_name="Should Not Run", confidence=0.9))
    persister = FakeDetectionPersister()
    fingerprint = FakeFingerprintAnnotator(FingerprintMatch(candidate_id=7, vector=[1, 2, 3], duration=30.0, score=1.0))
    transcriber = FakeTranscriber(text="known produced spot", wall_time_sec=3.0)
    consumer = ChunkConsumer(
        worker_db,
        settings,
        transcriber,
        extractor=extractor,
        detection_persister=persister,
        fingerprint_annotator=fingerprint,
    )

    assert consumer.run_once() is True

    assert fingerprint.calls == [(chunk_id, audio)]
    assert len(transcriber.calls) == 1
    assert extractor.calls == []
    assert persister.calls == []
    conn = get_connection(worker_db)
    try:
        chunk = conn.execute(
            "SELECT status, error FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        assert chunk["status"] == ChunkStatus.DONE.value
        assert chunk["error"] is None
        transcript = conn.execute(
            "SELECT text FROM transcripts WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        assert transcript["text"] == "known produced spot"
    finally:
        conn.close()


def test_drop_oldest_overflow_writes_gaps(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            # 3 hours of pending at 90s each = 120 chunks; keep newest 2h (80 chunks)
            for i in range(120):
                audio = tmp_path / f"chunk_{i}.wav"
                audio.write_bytes(b"x")
                _insert_chunk(
                    conn,
                    station_id=station_id,
                    path=str(audio),
                    start_ts=float(i * 90),
                    end_ts=float(i * 90 + 90),
                )
    finally:
        conn.close()

    transcriber = FakeTranscriber()
    consumer = ChunkConsumer(worker_db, settings, transcriber, poll_interval_sec=0.01)

    # run_once triggers drop-oldest then claims newest survivor
    assert consumer.run_once() is True

    conn = get_connection(worker_db)
    try:
        dropped = conn.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE status = 'dropped'"
        ).fetchone()["n"]
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE status = 'pending'"
        ).fetchone()["n"]
        done_or_processing = conn.execute(
            """
            SELECT COUNT(*) AS n FROM chunks
            WHERE status IN ('done', 'processing')
            """
        ).fetchone()["n"]

        assert dropped == 40
        assert pending == 79
        assert done_or_processing == 1

        gaps = conn.execute(
            "SELECT reason, start_ts, end_ts FROM gaps WHERE reason = 'dropped_backlog'"
        ).fetchall()
        assert len(gaps) == 1
        assert gaps[0]["start_ts"] == 0.0
        assert gaps[0]["end_ts"] == 3600.0
    finally:
        conn.close()


def test_atomic_claim_two_threads_never_duplicate(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            for i in range(4):
                audio = tmp_path / f"chunk_{i}.wav"
                audio.write_bytes(b"x")
                _insert_chunk(
                    conn,
                    station_id=station_id,
                    path=str(audio),
                    start_ts=float(i * 100),
                    end_ts=float(i * 100 + 90),
                )
    finally:
        conn.close()

    transcriber = FakeTranscriber(wall_time_sec=1.0)
    consumer = ChunkConsumer(worker_db, settings, transcriber)

    errors: list[Exception] = []

    def worker() -> None:
        try:
            for _ in range(4):
                consumer.run_once()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors

    conn = get_connection(worker_db)
    try:
        done_count = conn.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE status = 'done'"
        ).fetchone()["n"]
        transcript_count = conn.execute(
            "SELECT COUNT(*) AS n FROM transcripts"
        ).fetchone()["n"]
        assert done_count == 4
        assert transcript_count == 4
    finally:
        conn.close()


def test_missing_audio_file_dropped_loop_continues(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "gone.wav"
    present = tmp_path / "here.wav"
    present.write_bytes(b"x")

    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            _insert_chunk(
                conn,
                station_id=station_id,
                path=str(missing),
                start_ts=0.0,
                end_ts=90.0,
            )
            _insert_chunk(
                conn,
                station_id=station_id,
                path=str(present),
                start_ts=100.0,
                end_ts=190.0,
            )
    finally:
        conn.close()

    transcriber = FakeTranscriber()
    consumer = ChunkConsumer(worker_db, settings, transcriber)

    assert consumer.run_once() is True
    assert consumer.run_once() is True

    conn = get_connection(worker_db)
    try:
        rows = conn.execute(
            "SELECT path, status, error FROM chunks ORDER BY start_ts"
        ).fetchall()
        assert rows[0]["status"] == "dropped"
        assert "missing audio file" in rows[0]["error"]
        assert rows[1]["status"] == "done"
        assert len(transcriber.calls) == 1
    finally:
        conn.close()


def test_transcription_failure_dropped_loop_continues(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    bad = tmp_path / "bad.wav"
    good = tmp_path / "good.wav"
    bad.write_bytes(b"x")
    good.write_bytes(b"y")

    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            _insert_chunk(
                conn,
                station_id=station_id,
                path=str(bad),
                start_ts=0.0,
                end_ts=90.0,
            )
            _insert_chunk(
                conn,
                station_id=station_id,
                path=str(good),
                start_ts=100.0,
                end_ts=190.0,
            )
    finally:
        conn.close()

    transcriber = FakeTranscriber(fail_on={bad})
    consumer = ChunkConsumer(worker_db, settings, transcriber)

    assert consumer.run_once() is True
    assert consumer.run_once() is True

    conn = get_connection(worker_db)
    try:
        bad_row = conn.execute(
            "SELECT status, error FROM chunks WHERE path = ?", (str(bad),)
        ).fetchone()
        good_row = conn.execute(
            "SELECT status FROM chunks WHERE path = ?", (str(good),)
        ).fetchone()
        assert bad_row["status"] == "dropped"
        assert bad_row["error"] == "transcription failed"
        assert good_row["status"] == "done"
    finally:
        conn.close()


def test_run_once_returns_false_when_queue_empty(
    worker_db: Path,
    settings: PipelineSettings,
) -> None:
    transcriber = FakeTranscriber()
    consumer = ChunkConsumer(worker_db, settings, transcriber)
    assert consumer.run_once() is False


def test_extraction_failure_marks_chunk_dropped_but_keeps_transcript(
    worker_db: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    """ASR succeeds; extraction/dedup failure → dropped + error; transcript retained."""
    audio = tmp_path / "chunk.wav"
    audio.write_bytes(b"fake wav")

    conn = get_connection(worker_db)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _insert_chunk(
                conn,
                station_id=station_id,
                path=str(audio),
                start_ts=1000.0,
                end_ts=1090.0,
            )
    finally:
        conn.close()

    extractor = FakeExtractor(fail_with=RuntimeError("ollama unavailable"))
    persister = FakeDetectionPersister()
    transcriber = FakeTranscriber(text="some transcript", wall_time_sec=3.0)
    consumer = ChunkConsumer(
        worker_db,
        settings,
        transcriber,
        extractor=extractor,
        detection_persister=persister,
    )

    assert consumer.run_once() is True

    assert extractor.calls == ["some transcript"]
    assert persister.calls == []
    conn = get_connection(worker_db)
    try:
        chunk = conn.execute(
            "SELECT status, error FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        assert chunk["status"] == ChunkStatus.DROPPED.value
        assert "extraction/dedup failed" in chunk["error"]
        assert "ollama unavailable" in chunk["error"]
        transcript = conn.execute(
            "SELECT text FROM transcripts WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        assert transcript["text"] == "some transcript"
    finally:
        conn.close()
