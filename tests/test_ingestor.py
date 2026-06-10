"""Tests for Phase 2 ingestor: ffmpeg command, enqueue, gaps, and backoff."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import pytest

from ingestor.ffmpeg import (
    FfmpegChunkRunner,
    build_ffmpeg_command,
    get_wav_duration_seconds,
    is_valid_chunk_duration,
)
from ingestor.supervisor import (
    BackoffPolicy,
    StationIngestor,
    create_station_ingestors,
    run_station_ingestor,
    startup_stagger_delay_seconds,
    wait_startup_stagger,
)
from shared.db import get_connection, migrate
from shared.models import PipelineSettings, StationConfig


def _write_silent_wav(
    path: Path,
    duration_sec: float,
    *,
    sample_rate: int = 16000,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(sample_rate * duration_sec)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frame_count)


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeRunner:
    def __init__(
        self,
        *,
        returncode: int = 0,
        write_file: bool = True,
        wav_duration_sec: float | None = None,
        capture_elapsed_sec: float = 0.0,
        clock: FakeClock | None = None,
    ) -> None:
        self.returncode = returncode
        self.write_file = write_file
        self.wav_duration_sec = wav_duration_sec
        self.capture_elapsed_sec = capture_elapsed_sec
        self.clock = clock
        self.calls: list[tuple[StationConfig, Path, float]] = []

    def record_chunk(
        self,
        station: StationConfig,
        output_path: Path,
        *,
        duration_sec: float,
    ) -> int:
        self.calls.append((station, output_path, duration_sec))
        if self.clock is not None and self.capture_elapsed_sec > 0:
            self.clock.now += self.capture_elapsed_sec
        if self.write_file:
            wav_duration = (
                self.wav_duration_sec
                if self.wav_duration_sec is not None
                else duration_sec
            )
            _write_silent_wav(output_path, wav_duration)
        return self.returncode


def _conn(db_path: Path) -> sqlite3.Connection:
    return get_connection(db_path)


def test_build_ffmpeg_command_uses_reconnect_flags_and_chunk_duration(tmp_path: Path) -> None:
    station = StationConfig(
        name="news-talk",
        url="https://radio.example/stream.mp3",
        format="mp3",
    )
    output_path = tmp_path / "chunk.wav"
    settings = PipelineSettings(chunk_len=90, overlap=7)

    command = build_ffmpeg_command(station, output_path, settings)

    assert command[:2] == ["ffmpeg", "-hide_banner"]
    assert "-reconnect" in command
    assert "-reconnect_streamed" in command
    assert "-reconnect_at_eof" in command
    assert "-reconnect_delay_max" in command
    assert command[command.index("-i") + 1] == station.url
    assert command[command.index("-t") + 1] == "90"
    assert command[-1] == str(output_path)


def test_build_ffmpeg_command_omits_reconnect_at_eof_for_hls(tmp_path: Path) -> None:
    station = StationConfig(
        name="kprc-am-950",
        url="https://stream.revma.ihrhls.com/zc2277/hls.m3u8",
        format="aac",
    )
    command = build_ffmpeg_command(
        station, tmp_path / "chunk.wav", PipelineSettings(chunk_len=90)
    )

    assert "-reconnect" in command
    assert "-reconnect_streamed" in command
    assert "-reconnect_at_eof" not in command
    assert "-reconnect_delay_max" in command


def test_is_valid_chunk_duration_uses_two_second_tolerance(tmp_path: Path) -> None:
    path = tmp_path / "chunk.wav"
    _write_silent_wav(path, 88.0)
    assert is_valid_chunk_duration(path, 90.0) is True
    _write_silent_wav(path, 30.0)
    assert is_valid_chunk_duration(path, 90.0) is False


def test_successful_station_ingest_enqueues_pending_chunk_and_upserts_station(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Test FM", url="https://example.com/live", enabled=True)
    settings = PipelineSettings(chunk_len=90, overlap=7)
    runner = FakeRunner(returncode=0)
    clock = FakeClock(start=1_000.0)

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=1, max_seconds=8),
    )

    assert ingestor.run_once() is True

    output_path = Path(runner.calls[0][1])
    measured = get_wav_duration_seconds(output_path)
    assert measured is not None
    assert abs(measured - 90.0) <= 2.0

    conn = _conn(db_path)
    try:
        station_row = conn.execute(
            "SELECT id, name, url, enabled FROM stations WHERE name = ?",
            ("Test FM",),
        ).fetchone()
        assert station_row is not None
        assert station_row["url"] == "https://example.com/live"
        assert station_row["enabled"] == 1

        chunk = conn.execute("SELECT * FROM chunks").fetchone()
        assert chunk["station_id"] == station_row["id"]
        assert chunk["status"] == "pending"
        assert chunk["start_ts"] == 1_000.0
        assert chunk["end_ts"] == 1_090.0
        assert Path(chunk["path"]).is_file()
        assert "test-fm" in Path(chunk["path"]).parts
        assert conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0] == 0
    finally:
        conn.close()

    assert runner.calls[0][2] == 90
    assert clock.sleeps == [83]


def test_stride_accounts_for_recording_elapsed_with_valid_wav(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Stride FM", url="https://example.com/live", enabled=True)
    settings = PipelineSettings(chunk_len=90, overlap=7)
    clock = FakeClock(start=5_000.0)
    runner = FakeRunner(
        returncode=0,
        capture_elapsed_sec=7.0,
        clock=clock,
    )

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
    )

    assert ingestor.stride_seconds == 83.0
    assert ingestor.run_once() is True

    output_path = Path(runner.calls[0][1])
    with wave.open(str(output_path), "rb") as handle:
        measured_duration = handle.getnframes() / handle.getframerate()
    assert abs(measured_duration - 90.0) <= 2.0
    assert clock.sleeps == [76.0]


def test_partial_wav_logs_empty_chunk_gap_and_does_not_enqueue(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Partial FM", url="https://example.com/live")
    # ingest_immediate_retries=0 so the runner is only called once (tests single-attempt path)
    settings = PipelineSettings(chunk_len=90, overlap=7, ingest_immediate_retries=0)
    runner = FakeRunner(returncode=0, wav_duration_sec=30.0)
    clock = FakeClock(start=3_000.0)

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=4, max_seconds=16),
    )

    assert ingestor.run_once() is False

    conn = _conn(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
        gap = conn.execute("SELECT reason, start_ts, end_ts FROM gaps").fetchone()
        assert gap["reason"] == "empty_chunk"
        assert gap["start_ts"] == 3_000.0
        assert gap["end_ts"] == 3_090.0
    finally:
        conn.close()

    output_path = Path(runner.calls[0][1])
    assert not output_path.exists()
    assert clock.sleeps == [4]


def test_failed_ffmpeg_logs_stream_down_gap_and_exponential_backoff(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Broken AM", url="https://example.com/broken")
    # ingest_immediate_retries=0: single attempt per run_once call, tests pure backoff sequence
    settings = PipelineSettings(chunk_len=90, overlap=7, ingest_immediate_retries=0)
    runner = FakeRunner(returncode=1, write_file=False)
    clock = FakeClock(start=2_000.0)

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=5, max_seconds=20),
    )

    assert ingestor.run_once() is False
    assert ingestor.run_once() is False

    conn = _conn(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
        gaps = conn.execute(
            "SELECT reason, start_ts, end_ts FROM gaps ORDER BY id"
        ).fetchall()
        assert [gap["reason"] for gap in gaps] == ["stream_down", "stream_down"]
        assert gaps[0]["start_ts"] == 2_000.0
        assert gaps[0]["end_ts"] == 2_090.0
    finally:
        conn.close()

    assert clock.sleeps == [5, 10]


def test_ffmpeg_runner_terminate_active_stops_in_flight_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    station = StationConfig(name="Hang FM", url="https://example.com/live")
    runner = FfmpegChunkRunner(PipelineSettings(chunk_len=90, overlap=7))
    output_path = tmp_path / "hang.wav"
    hang_command = [sys.executable, "-c", "import time; time.sleep(120)"]

    def fake_popen_with_process_group(_command: list[str]) -> subprocess.Popen[bytes]:
        import os

        kwargs: dict[str, object] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["preexec_fn"] = os.setsid
        return subprocess.Popen(hang_command, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(
        "ingestor.ffmpeg._popen_with_process_group",
        fake_popen_with_process_group,
    )

    result: list[int] = []

    def record() -> None:
        result.append(runner.record_chunk(station, output_path, duration_sec=90.0))

    thread = threading.Thread(target=record)
    thread.start()
    time.sleep(0.5)
    runner.terminate_active()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert result
    assert result[0] != 0


# ---------------------------------------------------------------------------
# WP-ingest-resilience tests (RED first, then implemented)
# ---------------------------------------------------------------------------


class SequencedFakeRunner:
    """Runner whose return-code sequence can be set per-call.

    Pass ``returncodes`` as a list; each call pops the first entry.
    The last entry is repeated forever once the list is exhausted.
    ``write_file`` controls whether a full-duration WAV is written on success.
    """

    def __init__(
        self,
        returncodes: list[int],
        *,
        wav_duration_sec: float | None = None,
        clock: FakeClock | None = None,
    ) -> None:
        self._returncodes = list(returncodes)
        self.wav_duration_sec = wav_duration_sec
        self.clock = clock
        self.calls: list[tuple[StationConfig, Path, float]] = []

    def record_chunk(
        self,
        station: StationConfig,
        output_path: Path,
        *,
        duration_sec: float,
    ) -> int:
        self.calls.append((station, output_path, duration_sec))
        code = self._returncodes.pop(0) if self._returncodes else 0
        if code == 0:
            dur = self.wav_duration_sec if self.wav_duration_sec is not None else duration_sec
            _write_silent_wav(output_path, dur)
        return code


def test_immediate_retries_recover_without_gap(tmp_path: Path) -> None:
    """Fail twice then succeed: 1 chunk enqueued, 0 gaps, backoff reset."""
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Retry FM", url="https://example.com/live", enabled=True)
    settings = PipelineSettings(
        chunk_len=90,
        overlap=7,
        ingest_immediate_retries=3,
        ingest_immediate_retry_delay_sec=0.0,
        ingest_backoff_initial_sec=1,
        ingest_backoff_max_sec=30,
    )
    clock = FakeClock(start=1_000.0)
    # fail, fail, succeed
    runner = SequencedFakeRunner([1, 1, 0], clock=clock)

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=1, max_seconds=30),
    )

    result = ingestor.run_once()

    conn = _conn(db_path)
    try:
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        gaps = conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0]
    finally:
        conn.close()

    assert result is True, "run_once should return True on eventual success"
    assert chunks == 1, f"expected 1 chunk, got {chunks}"
    assert gaps == 0, f"expected 0 gaps, got {gaps}"
    # backoff should be reset — current_seconds is None after success
    assert ingestor.backoff.current_seconds is None, "backoff should be reset after recovery"
    assert len(runner.calls) == 3, f"expected 3 ffmpeg calls, got {len(runner.calls)}"


def test_immediate_retries_exhausted_logs_single_gap(tmp_path: Path) -> None:
    """All retries fail (3 immediate + 1 initial = 4 failures): exactly 1 gap, 0 chunks."""
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Dead Air", url="https://example.com/dead", enabled=True)
    settings = PipelineSettings(
        chunk_len=90,
        overlap=7,
        ingest_immediate_retries=3,
        ingest_immediate_retry_delay_sec=0.0,
        ingest_backoff_initial_sec=1,
        ingest_backoff_max_sec=30,
    )
    clock = FakeClock(start=5_000.0)
    # 4 failures: 1 initial + 3 immediate retries, all fail
    runner = SequencedFakeRunner([1, 1, 1, 1], clock=clock)

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(initial_seconds=1, max_seconds=30),
    )

    result = ingestor.run_once()

    conn = _conn(db_path)
    try:
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        gaps = conn.execute("SELECT reason FROM gaps").fetchall()
    finally:
        conn.close()

    assert result is False
    assert chunks == 0
    assert len(gaps) == 1, f"expected exactly 1 gap, got {len(gaps)}"
    assert gaps[0]["reason"] == "stream_down"
    assert len(runner.calls) == 4, f"expected 4 ffmpeg calls, got {len(runner.calls)}"


def test_backoff_uses_settings_defaults(tmp_path: Path) -> None:
    """After retries exhausted, backoff sleeps use ingest_backoff_initial_sec (1) then double (1, 2)."""
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    station = StationConfig(name="Slow AM", url="https://example.com/slow", enabled=True)
    settings = PipelineSettings(
        chunk_len=90,
        overlap=7,
        ingest_immediate_retries=0,          # no immediate retries — fail fast to backoff
        ingest_immediate_retry_delay_sec=0.0,
        ingest_backoff_initial_sec=1,
        ingest_backoff_max_sec=30,
    )
    clock = FakeClock(start=0.0)
    runner = SequencedFakeRunner([1, 1, 1], clock=clock)

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner=runner,
        clock=clock,
        backoff=BackoffPolicy(
            initial_seconds=settings.ingest_backoff_initial_sec,
            max_seconds=settings.ingest_backoff_max_sec,
        ),
    )

    ingestor.run_once()  # fail → backoff sleep 1
    ingestor.run_once()  # fail → backoff sleep 2

    backoff_sleeps = clock.sleeps
    assert backoff_sleeps == [1, 2], (
        f"expected backoff sleeps [1, 2] from settings, got {backoff_sleeps}"
    )


def test_create_station_ingestors_skips_disabled_stations(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    settings = PipelineSettings(chunk_len=90, overlap=7)
    stations = [
        StationConfig(name="enabled", url="https://example.com/enabled", enabled=True),
        StationConfig(name="disabled", url="https://example.com/disabled", enabled=False),
    ]

    ingestors = create_station_ingestors(
        db_path,
        stations,
        settings,
        chunks_dir=tmp_path / "chunks",
        runner_factory=lambda: FfmpegChunkRunner(),
    )

    assert [ingestor.station.name for ingestor in ingestors] == ["enabled"]


def test_startup_stagger_delay_seconds() -> None:
    assert startup_stagger_delay_seconds(0, 15) == 0.0
    assert startup_stagger_delay_seconds(1, 15) == 15.0
    assert startup_stagger_delay_seconds(8, 15) == 120.0
    assert startup_stagger_delay_seconds(2, 0) == 0.0


def test_wait_startup_stagger_honors_stop_event() -> None:
    stop_event = threading.Event()
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        stop_event.set()

    wait_startup_stagger(stop_event, 30.0, sleep_fn=fake_sleep, monotonic_fn=lambda: 0.0)
    assert slept == [0.5]


def test_run_station_ingestor_runs_after_stagger(monkeypatch: pytest.MonkeyPatch) -> None:
    stop_event = threading.Event()
    calls: list[str] = []

    class FakeIngestor:
        def run(self, event: threading.Event) -> None:
            calls.append("run")

    def fake_wait(_event: threading.Event, delay_sec: float) -> None:
        assert delay_sec == 2.0

    monkeypatch.setattr("ingestor.supervisor.wait_startup_stagger", fake_wait)

    run_station_ingestor(
        FakeIngestor(),  # type: ignore[arg-type]
        stop_event,
        startup_delay_sec=2.0,
    )
    assert calls == ["run"]
