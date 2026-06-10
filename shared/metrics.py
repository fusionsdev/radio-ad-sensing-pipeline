"""Prometheus metrics helpers for the pipeline services."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from prometheus_client import Counter, Gauge, start_http_server

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
