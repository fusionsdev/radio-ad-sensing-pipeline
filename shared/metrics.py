"""Prometheus metrics helpers for the pipeline services."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram, start_http_server

_STAGE_DURATION_BUCKETS = (
    0.1,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
    float("inf"),
)
_LLM_DURATION_BUCKETS = (0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf"))
_ASR_RTF_BUCKETS = (0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 5.0, float("inf"))

from shared.db import WalCheckpointResult, get_connection

QUEUE_PENDING_HOURS = Gauge(
    "pipeline_queue_pending_hours",
    "Total pending chunk duration in hours.",
)
CHUNKS_PROCESSED_TOTAL = Counter(
    "pipeline_chunks_processed_total",
    "Chunks processed by a pipeline service.",
    ["service"],
)
CHUNKS_DROPPED_TOTAL = Counter(
    "pipeline_chunks_dropped_total",
    "Chunks dropped while handling pipeline work.",
)
CHUNK_FILES_DELETED_TOTAL = Counter(
    "pipeline_chunk_files_deleted_total",
    "Transient chunk WAV files deleted by the janitor.",
)
ASR_RTF_AVG = Gauge(
    "pipeline_asr_rtf_avg",
    "Average ASR real-time factor.",
)
ASR_DURATION_SECONDS = Histogram(
    "pipeline_asr_duration_seconds",
    "Whisper transcription wall time per chunk.",
    ["station"],
    buckets=_STAGE_DURATION_BUCKETS,
)
ASR_RTF = Histogram(
    "pipeline_asr_rtf",
    "ASR real-time factor per chunk (wall time / audio duration).",
    ["station"],
    buckets=_ASR_RTF_BUCKETS,
)
STAGE_DURATION_SECONDS = Histogram(
    "pipeline_stage_duration_seconds",
    "Wall time spent in a pipeline processing stage.",
    ["stage"],
    buckets=_STAGE_DURATION_BUCKETS,
)
LLM_EXTRACTION_DURATION_SECONDS = Histogram(
    "pipeline_llm_extraction_duration_seconds",
    "Ollama structured extraction wall time in seconds.",
    buckets=_LLM_DURATION_BUCKETS,
)
DETECTIONS_TOTAL = Counter(
    "pipeline_detections_total",
    "Ad detections persisted above the confidence threshold.",
)
INGEST_CHUNKS_TOTAL = Counter(
    "pipeline_ingest_chunks_total",
    "Audio chunks successfully enqueued by the ingestor.",
    ["station"],
)
INGEST_ERRORS_TOTAL = Counter(
    "pipeline_ingest_errors_total",
    "Ingest failures that logged a gap before backoff.",
    ["station", "reason"],
)
DEDUP_MATCHES_TOTAL = Counter(
    "pipeline_dedup_matches_total",
    "Canonical ad matches during deduplication.",
    ["match_type"],
)
DEDUP_SUPPRESSED_TOTAL = Counter(
    "pipeline_dedup_suppressed_total",
    "Detections suppressed by the same-station airing window.",
)
FINGERPRINT_HITS_TOTAL = Counter(
    "pipeline_fingerprint_hits_total",
    "Chunks short-circuited by a known-ad fingerprint match.",
)
FINGERPRINT_ERRORS_TOTAL = Counter(
    "pipeline_fingerprint_errors_total",
    "Fingerprint annotation failures that fell back to ASR/LLM.",
)
CHUNKS_BY_STATUS = Gauge(
    "pipeline_chunks_by_status",
    "Chunk count grouped by queue status.",
    ["status"],
)
ALERTS_SENT_TOTAL = Counter(
    "pipeline_alerts_sent_total",
    "Telegram alerts emitted by the alerter service.",
    ["alert_type", "outcome"],
)
STATION_LAST_CHUNK_TIMESTAMP_SECONDS = Gauge(
    "pipeline_station_last_chunk_timestamp_seconds",
    "Last chunk timestamp seen for each station.",
    ["station"],
)
STATION_ENABLED = Gauge(
    "pipeline_station_enabled",
    "1 when station is enabled for live ingest.",
    ["station"],
)
SQLITE_WAL_LOG_FRAMES = Gauge(
    "pipeline_sqlite_wal_log_frames",
    "WAL log frame count after the last checkpoint attempt.",
)
SQLITE_WAL_CHECKPOINTED_FRAMES = Gauge(
    "pipeline_sqlite_wal_checkpointed_frames",
    "WAL frames checkpointed in the last passive checkpoint run.",
)
SQLITE_WAL_BUSY = Gauge(
    "pipeline_sqlite_wal_busy",
    "1 when the last wal_checkpoint(PASSIVE) could not finish due to readers/writers.",
)

_STARTED_PORTS: set[int] = set()
_STARTED_PORTS_LOCK = threading.Lock()

_DASHBOARD_REFRESH_LOCK = threading.Lock()
_DASHBOARD_REFRESH_DB_PATH: Path | None = None
_DASHBOARD_REFRESH_INTERVAL_SECONDS = 30.0
_DASHBOARD_REFRESH_THREAD: threading.Thread | None = None


def start_metrics_server(port: int) -> None:
    """Start the Prometheus scrape endpoint once per process."""
    with _STARTED_PORTS_LOCK:
        if port in _STARTED_PORTS:
            return
        start_http_server(port)
        _STARTED_PORTS.add(port)


def increment_chunks_processed(service: str, amount: float = 1.0) -> None:
    CHUNKS_PROCESSED_TOTAL.labels(service=service).inc(amount)


def increment_chunks_dropped(amount: float = 1.0) -> None:
    CHUNKS_DROPPED_TOTAL.inc(amount)


def increment_chunk_files_deleted(amount: float = 1.0) -> None:
    CHUNK_FILES_DELETED_TOTAL.inc(amount)


def set_asr_rtf_avg(value: float) -> None:
    ASR_RTF_AVG.set(value)


def observe_asr_metrics(station: str, wall_time_sec: float, rtf: float) -> None:
    ASR_DURATION_SECONDS.labels(station=station).observe(wall_time_sec)
    ASR_RTF.labels(station=station).observe(rtf)


def observe_stage_duration(stage: str, duration_sec: float) -> None:
    STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_sec)


def observe_llm_extraction_duration(duration_sec: float) -> None:
    LLM_EXTRACTION_DURATION_SECONDS.observe(duration_sec)


def increment_detections(amount: float = 1.0) -> None:
    DETECTIONS_TOTAL.inc(amount)


def increment_ingest_chunks(station: str, amount: float = 1.0) -> None:
    INGEST_CHUNKS_TOTAL.labels(station=station).inc(amount)


def increment_ingest_errors(station: str, reason: str, amount: float = 1.0) -> None:
    INGEST_ERRORS_TOTAL.labels(station=station, reason=reason).inc(amount)


def increment_dedup_matches(match_type: str, amount: float = 1.0) -> None:
    DEDUP_MATCHES_TOTAL.labels(match_type=match_type).inc(amount)


def increment_dedup_suppressed(amount: float = 1.0) -> None:
    DEDUP_SUPPRESSED_TOTAL.inc(amount)


def increment_fingerprint_hits(amount: float = 1.0) -> None:
    FINGERPRINT_HITS_TOTAL.inc(amount)


def increment_fingerprint_errors(amount: float = 1.0) -> None:
    FINGERPRINT_ERRORS_TOTAL.inc(amount)


def increment_alerts_sent(alert_type: str, outcome: str, amount: float = 1.0) -> None:
    ALERTS_SENT_TOTAL.labels(alert_type=alert_type, outcome=outcome).inc(amount)


def refresh_chunks_by_status(db_path: str | Path) -> None:
    conn = None
    rows = []
    try:
        conn = get_connection(db_path, read_only=True)
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS chunk_count
            FROM chunks
            GROUP BY status
            """
        ).fetchall()
    except Exception:
        rows = []
    finally:
        if conn is not None:
            conn.close()

    seen: set[str] = set()
    for row in rows:
        status = str(row["status"])
        CHUNKS_BY_STATUS.labels(status=status).set(float(row["chunk_count"]))
        seen.add(status)
    for status in ("pending", "processing", "done", "dropped"):
        if status not in seen:
            CHUNKS_BY_STATUS.labels(status=status).set(0.0)


def set_station_last_chunk_timestamp(station: str, timestamp: float) -> None:
    STATION_LAST_CHUNK_TIMESTAMP_SECONDS.labels(station=station).set(timestamp)


def set_station_enabled(station: str, enabled: bool) -> None:
    STATION_ENABLED.labels(station=station).set(1 if enabled else 0)


def remove_station_last_chunk_timestamp(station: str) -> None:
    try:
        STATION_LAST_CHUNK_TIMESTAMP_SECONDS.remove(station)
    except KeyError:
        pass


def set_wal_checkpoint_metrics(result: WalCheckpointResult) -> None:
    SQLITE_WAL_LOG_FRAMES.set(result.log_frames)
    SQLITE_WAL_CHECKPOINTED_FRAMES.set(result.checkpointed_frames)
    SQLITE_WAL_BUSY.set(1 if result.busy else 0)


def set_queue_pending_hours(db_path: str | Path) -> None:
    pending_seconds = 0.0
    conn = None
    try:
        conn = get_connection(db_path, read_only=True)
        row = conn.execute(
            """
            SELECT COALESCE(SUM(end_ts - start_ts), 0.0) AS pending_seconds
            FROM chunks
            WHERE status = 'pending'
            """
        ).fetchone()
        pending_seconds = float(row["pending_seconds"] if row is not None else 0.0)
    except Exception:
        pending_seconds = 0.0
    finally:
        if conn is not None:
            conn.close()
    QUEUE_PENDING_HOURS.set(pending_seconds / 3600.0)


def refresh_station_metrics(db_path: str | Path) -> None:
    conn = None
    rows = []
    try:
        conn = get_connection(db_path, read_only=True)
        rows = conn.execute(
            """
            SELECT s.name AS station_name, s.enabled, MAX(c.end_ts) AS last_chunk_ts
            FROM stations s
            LEFT JOIN chunks c ON c.station_id = s.id
            GROUP BY s.id, s.name, s.enabled
            ORDER BY s.name
            """
        ).fetchall()
    except Exception:
        rows = []
    finally:
        if conn is not None:
            conn.close()

    for row in rows:
        station_name = row["station_name"]
        enabled = bool(row["enabled"])
        set_station_enabled(station_name, enabled)
        if not enabled:
            remove_station_last_chunk_timestamp(station_name)
            continue
        last_chunk_ts = row["last_chunk_ts"]
        if last_chunk_ts is None:
            continue
        set_station_last_chunk_timestamp(station_name, float(last_chunk_ts))


def refresh_dashboard_metrics(db_path: str | Path) -> None:
    set_queue_pending_hours(db_path)
    refresh_station_metrics(db_path)
    refresh_chunks_by_status(db_path)


def configure_dashboard_metrics(
    db_path: str | Path,
    *,
    refresh_interval_seconds: float = _DASHBOARD_REFRESH_INTERVAL_SECONDS,
) -> None:
    """Refresh dashboard gauges periodically in a background thread."""
    global _DASHBOARD_REFRESH_DB_PATH, _DASHBOARD_REFRESH_THREAD
    _DASHBOARD_REFRESH_DB_PATH = Path(db_path)

    with _DASHBOARD_REFRESH_LOCK:
        if _DASHBOARD_REFRESH_THREAD is not None and _DASHBOARD_REFRESH_THREAD.is_alive():
            return

        def _run() -> None:
            while True:
                current_db_path = _DASHBOARD_REFRESH_DB_PATH
                if current_db_path is not None:
                    refresh_dashboard_metrics(current_db_path)
                time.sleep(refresh_interval_seconds)

        _DASHBOARD_REFRESH_THREAD = threading.Thread(
            target=_run,
            name="dashboard-metrics-refresh",
            daemon=True,
        )
        _DASHBOARD_REFRESH_THREAD.start()
