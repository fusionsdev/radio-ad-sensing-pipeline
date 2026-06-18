"""Station-level ingestor supervisor with chunk enqueueing and gap logging."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ingestor.ffmpeg import (
    ChunkRunner,
    FfmpegChunkRunner,
    get_wav_duration_seconds,
    is_valid_chunk_duration,
)
from ingestor.repository import enqueue_chunk, is_station_enabled, log_gap, upsert_station
from shared.metrics import (
    increment_chunks_processed,
    increment_ingest_chunks,
    increment_ingest_errors,
    set_station_last_chunk_timestamp,
)
from shared.models import PipelineSettings, StationConfig

logger = logging.getLogger("ingestor")


class Clock(Protocol):
    def time(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class BackoffPolicy:
    """Exponential backoff state for one station supervisor."""

    initial_seconds: float = 5.0
    max_seconds: float = 300.0
    current_seconds: float | None = None

    def next_delay(self) -> float:
        if self.current_seconds is None:
            self.current_seconds = self.initial_seconds
        else:
            self.current_seconds = min(self.current_seconds * 2, self.max_seconds)
        return self.current_seconds

    def reset(self) -> None:
        self.current_seconds = None


class StationIngestor:
    """Record chunks for one station and enqueue successful outputs."""

    def __init__(
        self,
        db_path: str | Path,
        station: StationConfig,
        settings: PipelineSettings,
        *,
        chunks_dir: str | Path = Path("data/chunks"),
        runner: ChunkRunner | None = None,
        clock: Clock | None = None,
        backoff: BackoffPolicy | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.station = station
        self.settings = settings
        self.chunks_dir = Path(chunks_dir)
        self.runner = runner or FfmpegChunkRunner(settings)
        self.clock = clock or SystemClock()
        self.backoff = backoff or BackoffPolicy()
        self.restart_event = threading.Event()
        self.stop_event = threading.Event()

    def request_restart(self) -> None:
        """Interrupt in-flight ffmpeg and reset backoff on next loop iteration."""
        terminate = getattr(self.runner, "terminate_active", None)
        if callable(terminate):
            terminate()
        self.restart_event.set()

    def request_stop(self) -> None:
        """Stop this station ingestor thread and terminate in-flight ffmpeg."""
        terminate = getattr(self.runner, "terminate_active", None)
        if callable(terminate):
            terminate()
        self.stop_event.set()

    def _apply_restart(self) -> None:
        self.backoff.reset()
        self.restart_event.clear()

    def _sleep_interruptible(self, seconds: float, stop_event: threading.Event | None = None) -> None:
        if seconds <= 0:
            return
        deadline = self.clock.time() + seconds
        while self.clock.time() < deadline:
            if self.restart_event.is_set():
                return
            if self.stop_event.is_set():
                return
            if stop_event is not None and stop_event.is_set():
                return
            remaining = deadline - self.clock.time()
            if remaining <= 0:
                return
            self.clock.sleep(min(0.5, remaining))

    @property
    def stride_seconds(self) -> float:
        return max(float(self.settings.chunk_len - self.settings.overlap), 0.0)

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Run until stopped. Intended as a thread target per enabled station."""
        while (stop_event is None or not stop_event.is_set()) and not self.stop_event.is_set():
            if self.restart_event.is_set():
                self._apply_restart()
            self.run_once(stop_event)
            if stop_event is not None and stop_event.is_set():
                break
            if self.stop_event.is_set():
                break

    def run_once(self, stop_event: threading.Event | None = None) -> bool:
        """Record and enqueue one chunk.

        On first failure: immediately retries up to ``ingest_immediate_retries``
        times (with ``ingest_immediate_retry_delay_sec`` sleep between each)
        before logging a gap and entering exponential backoff.

        Returns True when a chunk was successfully enqueued, False when all
        attempts (initial + immediate retries) failed and a gap was logged.
        """
        start_ts = self.clock.time()
        expected_end_ts = start_ts + float(self.settings.chunk_len)
        output_path = self._output_path(start_ts)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        max_attempts = 1 + self.settings.ingest_immediate_retries  # initial + retries
        retry_delay = float(self.settings.ingest_immediate_retry_delay_sec)

        last_returncode: int = -1
        succeeded = False
        # Time the winning attempt actually began recording. With immediate
        # retries the loop-entry start_ts can predate the captured audio by
        # several attempts, so the enqueued window must track the real attempt.
        chunk_start_ts = start_ts

        for attempt in range(max_attempts):
            if self.restart_event.is_set():
                self._apply_restart()
                return False
            if self.stop_event.is_set():
                return False
            if stop_event is not None and stop_event.is_set():
                return False
            if attempt > 0:
                # Brief sleep between immediate retry attempts
                if retry_delay > 0:
                    self.clock.sleep(retry_delay)
                # Clean up any partial output from the previous attempt
                if output_path.exists():
                    output_path.unlink(missing_ok=True)

            logger.info(
                "starting station chunk",
                extra={
                    "station": self.station.name,
                    "path": str(output_path),
                    "attempt": attempt + 1,
                },
            )
            attempt_start_ts = self.clock.time()
            last_returncode = self.runner.record_chunk(
                self.station,
                output_path,
                duration_sec=float(self.settings.chunk_len),
            )

            chunk_len = float(self.settings.chunk_len)
            has_output = output_path.is_file() and output_path.stat().st_size > 0
            duration_ok = has_output and is_valid_chunk_duration(output_path, chunk_len)

            if last_returncode == 0 and duration_ok:
                succeeded = True
                chunk_start_ts = attempt_start_ts
                break

        if succeeded:
            # Derive the chunk window from the actual recorded duration rather
            # than the configured length so downstream airing-window dedup and
            # gap accounting use real timestamps.
            actual_duration = get_wav_duration_seconds(output_path)
            chunk_end_ts = chunk_start_ts + (
                actual_duration if actual_duration is not None else float(self.settings.chunk_len)
            )
            if not is_station_enabled(self.db_path, self.station.name):
                if output_path.exists():
                    output_path.unlink(missing_ok=True)
                logger.info(
                    "chunk discarded for disabled station",
                    extra={"station": self.station.name},
                )
                return False
            station_id = upsert_station(self.db_path, self.station)
            enqueue_chunk(
                self.db_path,
                station_id=station_id,
                path=str(output_path),
                start_ts=chunk_start_ts,
                end_ts=chunk_end_ts,
            )
            self.backoff.reset()
            set_station_last_chunk_timestamp(self.station.name, chunk_end_ts)
            increment_chunks_processed("ingestor")
            increment_ingest_chunks(self.station.name)
            self._sleep_interruptible(self._stride_delay(start_ts), stop_event)
            if self.restart_event.is_set():
                self._apply_restart()
                return True
            logger.info(
                "chunk enqueued",
                extra={
                    "station": self.station.name,
                    "path": str(output_path),
                    "start_ts": chunk_start_ts,
                    "end_ts": chunk_end_ts,
                },
            )
            return True

        # All attempts exhausted — log ONE gap, then enter exponential backoff.
        # Span at least the intended chunk window, but extend to the real
        # give-up time so immediate retries that burn minutes are not
        # under-reported as a single chunk-length of dead air.
        reason = "stream_down" if last_returncode != 0 else "empty_chunk"
        gap_end_ts = max(expected_end_ts, self.clock.time())
        station_id = upsert_station(self.db_path, self.station)
        log_gap(
            self.db_path,
            station_id=station_id,
            start_ts=start_ts,
            end_ts=gap_end_ts,
            reason=reason,
        )
        increment_ingest_errors(self.station.name, reason)
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        delay = self.backoff.next_delay()
        logger.warning(
            "station ingest failed",
            extra={
                "station": self.station.name,
                "returncode": last_returncode,
                "reason": reason,
                "backoff_seconds": delay,
                "attempts": max_attempts,
            },
        )
        self._sleep_interruptible(delay, stop_event)
        if self.restart_event.is_set():
            self._apply_restart()
        return False

    def _stride_delay(self, start_ts: float) -> float:
        elapsed = max(self.clock.time() - start_ts, 0.0)
        return max(self.stride_seconds - elapsed, 0.0)

    def _sleep_until_next_stride(self, start_ts: float) -> None:
        delay = self._stride_delay(start_ts)
        if delay > 0:
            self.clock.sleep(delay)

    def _output_path(self, start_ts: float) -> Path:
        station_slug = slugify_station_name(self.station.name)
        millis = int(start_ts * 1000)
        return self.chunks_dir / station_slug / f"{millis}.wav"


def slugify_station_name(name: str) -> str:
    """Make a station name safe for chunk directory names."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "station"


def startup_stagger_delay_seconds(index: int, stagger_sec: float) -> float:
    """Seconds to wait before station *index* begins its first chunk."""
    if index <= 0 or stagger_sec <= 0:
        return 0.0
    return index * stagger_sec


def wait_startup_stagger(
    stop_event: threading.Event,
    delay_sec: float,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> None:
    """Sleep up to delay_sec unless stop_event is already set."""
    if delay_sec <= 0 or stop_event.is_set():
        return
    deadline = monotonic_fn() + delay_sec
    while monotonic_fn() < deadline:
        if stop_event.is_set():
            return
        sleep_fn(min(0.5, deadline - monotonic_fn()))


def run_station_ingestor(
    ingestor: StationIngestor,
    stop_event: threading.Event,
    *,
    startup_delay_sec: float = 0.0,
) -> None:
    """Thread target: optional stagger delay, then run until stopped."""
    wait_startup_stagger(stop_event, startup_delay_sec)
    if not stop_event.is_set() and not ingestor.stop_event.is_set():
        ingestor.run(stop_event)


def spawn_station_ingestor(
    *,
    db_path: str | Path,
    station: StationConfig,
    settings: PipelineSettings,
    chunks_dir: str | Path,
    ingestors: dict[str, StationIngestor],
    threads: dict[str, threading.Thread],
    stop_event: threading.Event,
    startup_delay_sec: float = 0.0,
) -> StationIngestor:
    """Start a new ingestor thread for one station if not already running."""
    existing = ingestors.get(station.name)
    if existing is not None and not existing.stop_event.is_set():
        return existing

    ingestor = StationIngestor(
        db_path,
        station,
        settings,
        chunks_dir=chunks_dir,
        backoff=BackoffPolicy(
            initial_seconds=float(settings.ingest_backoff_initial_sec),
            max_seconds=float(settings.ingest_backoff_max_sec),
        ),
    )
    ingestors[station.name] = ingestor
    thread = threading.Thread(
        target=run_station_ingestor,
        args=(ingestor, stop_event),
        kwargs={"startup_delay_sec": startup_delay_sec},
        name=f"ingestor-{station.name}",
        daemon=True,
    )
    threads[station.name] = thread
    thread.start()
    return ingestor


def create_station_ingestors(
    db_path: str | Path,
    stations: list[StationConfig],
    settings: PipelineSettings,
    *,
    chunks_dir: str | Path = Path("data/chunks"),
    runner_factory: Callable[[], ChunkRunner] | None = None,
) -> list[StationIngestor]:
    """Build one ingestor per enabled station.

    BackoffPolicy is constructed from PipelineSettings so that
    ingest_backoff_initial_sec / ingest_backoff_max_sec override the
    hardcoded dataclass defaults.
    """
    enabled = [station for station in stations if station.enabled]
    ingestors: list[StationIngestor] = []
    for station in enabled:
        runner = runner_factory() if runner_factory is not None else FfmpegChunkRunner(settings)
        backoff = BackoffPolicy(
            initial_seconds=float(settings.ingest_backoff_initial_sec),
            max_seconds=float(settings.ingest_backoff_max_sec),
        )
        ingestors.append(
            StationIngestor(
                db_path,
                station,
                settings,
                chunks_dir=chunks_dir,
                runner=runner,
                backoff=backoff,
            )
        )
    return ingestors
