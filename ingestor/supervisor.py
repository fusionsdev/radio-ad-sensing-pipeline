"""Station-level ingestor supervisor with chunk enqueueing and gap logging."""

from __future__ import annotations

import logging
import hashlib
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ingestor.ffmpeg import ChunkRunner, FfmpegChunkRunner, is_valid_chunk_duration
from ingestor.repository import (
    enqueue_chunk,
    is_station_enabled,
    log_gap,
    upsert_station,
    upsert_station_ingest_health,
)
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


@dataclass
class StationIngestHealth:
    """In-memory circuit-breaker state for one station stream."""

    empty_chunk_threshold: int
    window_seconds: float
    attempt_threshold: int
    pause_seconds: float
    last_success_at: float | None = None
    last_failure_at: float | None = None
    consecutive_empty_chunks: int = 0
    consecutive_stream_down: int = 0
    attempts_since_success: int = 0
    backoff_until: float | None = None
    last_ffmpeg_error_sample: str = ""
    empty_chunk_failures: deque[float] = field(default_factory=deque)

    def record_success(self, success_ts: float) -> None:
        self.last_success_at = success_ts
        self.consecutive_empty_chunks = 0
        self.consecutive_stream_down = 0
        self.attempts_since_success = 0
        self.backoff_until = None
        self.last_ffmpeg_error_sample = ""
        self.empty_chunk_failures.clear()

    def record_failure(
        self,
        *,
        reason: str,
        failure_ts: float,
        attempt_count: int,
        ffmpeg_error_sample: str,
    ) -> None:
        self.last_failure_at = failure_ts
        self.attempts_since_success += max(attempt_count, 0)
        if reason == "empty_chunk":
            self.consecutive_empty_chunks += 1
            self.consecutive_stream_down = 0
            self.empty_chunk_failures.append(failure_ts)
        elif reason == "stream_down":
            self.consecutive_stream_down += 1
            self.consecutive_empty_chunks = 0
        else:
            self.consecutive_empty_chunks = 0
            self.consecutive_stream_down = 0
        if ffmpeg_error_sample:
            self.last_ffmpeg_error_sample = ffmpeg_error_sample
        self._prune_empty_chunk_failures(failure_ts)

    def mark_backoff(self, until_ts: float) -> None:
        self.backoff_until = until_ts

    def clear_backoff(self) -> None:
        self.backoff_until = None

    def should_pause_for_bad_stream(self, now_ts: float) -> bool:
        self._prune_empty_chunk_failures(now_ts)
        empty_chunk_trigger = (
            self.empty_chunk_threshold > 0
            and len(self.empty_chunk_failures) >= self.empty_chunk_threshold
        )
        attempt_trigger = (
            self.attempt_threshold > 0
            and self.attempts_since_success >= self.attempt_threshold
        )
        return empty_chunk_trigger or attempt_trigger

    def _prune_empty_chunk_failures(self, now_ts: float) -> None:
        cutoff = now_ts - max(self.window_seconds, 0.0)
        while self.empty_chunk_failures and self.empty_chunk_failures[0] < cutoff:
            self.empty_chunk_failures.popleft()


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
        self.url_hash = hashlib.sha256(station.url.encode("utf-8")).hexdigest()[:12]
        self.health = StationIngestHealth(
            empty_chunk_threshold=int(settings.ingest_bad_stream_empty_threshold),
            window_seconds=float(settings.ingest_bad_stream_window_minutes) * 60.0,
            attempt_threshold=int(settings.ingest_bad_stream_attempt_threshold),
            pause_seconds=float(settings.ingest_bad_stream_pause_minutes) * 60.0,
        )
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
        self.health.clear_backoff()
        self._persist_health("degraded", now_ts=self.clock.time())
        self.restart_event.clear()

    def _persist_health(
        self,
        status: str,
        *,
        now_ts: float,
        enabled: bool | None = None,
    ) -> None:
        try:
            upsert_station_ingest_health(
                self.db_path,
                station=self.station,
                status=status,
                now_ts=now_ts,
                last_success_at=self.health.last_success_at,
                last_failure_at=self.health.last_failure_at,
                consecutive_empty_chunks=self.health.consecutive_empty_chunks,
                consecutive_stream_down=self.health.consecutive_stream_down,
                attempts_since_success=self.health.attempts_since_success,
                backoff_until=self.health.backoff_until,
                last_ffmpeg_error_sample=self.health.last_ffmpeg_error_sample,
                url_hash=self.url_hash,
                enabled=enabled,
            )
        except Exception:
            logger.warning(
                "station health update failed",
                extra={"station": self.station.name, "status": status},
                exc_info=True,
            )

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
                break

        if succeeded:
            if not is_station_enabled(self.db_path, self.station.name):
                if output_path.exists():
                    output_path.unlink(missing_ok=True)
                self.health.clear_backoff()
                self._persist_health("paused", now_ts=self.clock.time(), enabled=False)
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
                start_ts=start_ts,
                end_ts=expected_end_ts,
            )
            self.backoff.reset()
            self.health.record_success(expected_end_ts)
            self._persist_health("healthy", now_ts=max(self.clock.time(), expected_end_ts))
            set_station_last_chunk_timestamp(self.station.name, expected_end_ts)
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
                    "start_ts": start_ts,
                    "end_ts": expected_end_ts,
                },
            )
            return True

        # All attempts exhausted — log ONE gap, then enter exponential backoff
        reason = "stream_down" if last_returncode != 0 else "empty_chunk"
        station_id = upsert_station(self.db_path, self.station, sync_enabled=False)
        log_gap(
            self.db_path,
            station_id=station_id,
            start_ts=start_ts,
            end_ts=expected_end_ts,
            reason=reason,
        )
        increment_ingest_errors(self.station.name, reason)
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        ffmpeg_error_sample = str(getattr(self.runner, "last_error_sample", "") or "")
        failure_ts = self.clock.time()
        self.health.record_failure(
            reason=reason,
            failure_ts=failure_ts,
            attempt_count=max_attempts,
            ffmpeg_error_sample=ffmpeg_error_sample,
        )
        short_delay = self.backoff.next_delay()
        should_pause = self.health.should_pause_for_bad_stream(failure_ts)
        delay = max(self.health.pause_seconds, short_delay) if should_pause else short_delay
        self.health.mark_backoff(failure_ts + delay)
        health_status = "backoff" if should_pause else "degraded"
        self._persist_health(health_status, now_ts=failure_ts)
        logger.warning(
            "station ingest failed",
            extra={
                "station": self.station.name,
                "url_hash": self.url_hash,
                "returncode": last_returncode,
                "reason": reason,
                "backoff_seconds": delay,
                "health_status": health_status,
                "backoff_until": self.health.backoff_until,
                "consecutive_empty_chunks": self.health.consecutive_empty_chunks,
                "consecutive_stream_down": self.health.consecutive_stream_down,
                "attempts_since_success": self.health.attempts_since_success,
                "ffmpeg_error_sample": ffmpeg_error_sample,
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
