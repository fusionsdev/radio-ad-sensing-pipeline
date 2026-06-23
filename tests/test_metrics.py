"""Tests for Prometheus metric helpers."""

from __future__ import annotations

from pathlib import Path

from shared.db import WalCheckpointResult, get_connection, migrate, transaction
from shared.metrics import (
    ALERTS_SENT_TOTAL,
    ASR_DURATION_SECONDS,
    ASR_RTF,
    CHUNKS_BY_STATUS,
    DEDUP_MATCHES_TOTAL,
    DEDUP_SUPPRESSED_TOTAL,
    DETECTIONS_TOTAL,
    FINGERPRINT_ERRORS_TOTAL,
    FINGERPRINT_HITS_TOTAL,
    INGEST_CHUNKS_TOTAL,
    INGEST_ERRORS_TOTAL,
    LLM_EXTRACTION_DURATION_SECONDS,
    SQLITE_WAL_BUSY,
    SQLITE_WAL_CHECKPOINTED_FRAMES,
    SQLITE_WAL_LOG_FRAMES,
    STAGE_DURATION_SECONDS,
    WORKER_CHUNKS_CLAIMED_TOTAL,
    WORKER_CHUNKS_PROCESSED_TOTAL,
    WORKER_DUPLICATE_TRANSCRIPT_TOTAL,
    WORKER_STALE_PROCESSING_RECOVERED_TOTAL,
    increment_alerts_sent,
    increment_dedup_matches,
    increment_dedup_suppressed,
    increment_detections,
    increment_fingerprint_errors,
    increment_fingerprint_hits,
    increment_ingest_chunks,
    increment_ingest_errors,
    increment_worker_chunks_claimed,
    increment_worker_chunks_processed,
    increment_worker_duplicate_transcript,
    increment_worker_stale_processing_recovered,
    observe_asr_metrics,
    observe_llm_extraction_duration,
    observe_stage_duration,
    refresh_chunks_by_status,
    set_wal_checkpoint_metrics,
)


def test_set_wal_checkpoint_metrics_updates_gauges() -> None:
    set_wal_checkpoint_metrics(
        WalCheckpointResult(busy=True, log_frames=12, checkpointed_frames=7)
    )
    assert SQLITE_WAL_LOG_FRAMES._value.get() == 12.0  # noqa: SLF001
    assert SQLITE_WAL_CHECKPOINTED_FRAMES._value.get() == 7.0  # noqa: SLF001
    assert SQLITE_WAL_BUSY._value.get() == 1.0  # noqa: SLF001

    set_wal_checkpoint_metrics(
        WalCheckpointResult(busy=False, log_frames=0, checkpointed_frames=0)
    )
    assert SQLITE_WAL_BUSY._value.get() == 0.0  # noqa: SLF001


def test_observe_stage_duration_records_histogram() -> None:
    before = STAGE_DURATION_SECONDS.labels(stage="asr")._sum.get()  # noqa: SLF001
    observe_stage_duration("asr", 1.25)
    after = STAGE_DURATION_SECONDS.labels(stage="asr")._sum.get()  # noqa: SLF001
    assert after == before + 1.25


def test_observe_llm_extraction_duration_records_histogram() -> None:
    before = LLM_EXTRACTION_DURATION_SECONDS._sum.get()  # noqa: SLF001
    observe_llm_extraction_duration(2.5)
    after = LLM_EXTRACTION_DURATION_SECONDS._sum.get()  # noqa: SLF001
    assert after == before + 2.5


def test_increment_detections_increments_counter() -> None:
    before = DETECTIONS_TOTAL._value.get()  # noqa: SLF001
    increment_detections()
    after = DETECTIONS_TOTAL._value.get()  # noqa: SLF001
    assert after == before + 1.0


def test_observe_asr_metrics_records_station_histograms() -> None:
    duration_before = ASR_DURATION_SECONDS.labels(station="kfi-am-640")._sum.get()  # noqa: SLF001
    rtf_before = ASR_RTF.labels(station="kfi-am-640")._sum.get()  # noqa: SLF001
    observe_asr_metrics("kfi-am-640", 12.0, 0.13)
    duration_after = ASR_DURATION_SECONDS.labels(station="kfi-am-640")._sum.get()  # noqa: SLF001
    rtf_after = ASR_RTF.labels(station="kfi-am-640")._sum.get()  # noqa: SLF001
    assert duration_after == duration_before + 12.0
    assert rtf_after == rtf_before + 0.13


def test_ingest_metrics_use_station_and_reason_labels() -> None:
    chunks_before = INGEST_CHUNKS_TOTAL.labels(station="wbap-am-820")._value.get()  # noqa: SLF001
    errors_before = INGEST_ERRORS_TOTAL.labels(station="wbap-am-820", reason="stream_down")._value.get()  # noqa: SLF001
    increment_ingest_chunks("wbap-am-820")
    increment_ingest_errors("wbap-am-820", "stream_down")
    assert INGEST_CHUNKS_TOTAL.labels(station="wbap-am-820")._value.get() == chunks_before + 1.0  # noqa: SLF001
    assert INGEST_ERRORS_TOTAL.labels(station="wbap-am-820", reason="stream_down")._value.get() == errors_before + 1.0  # noqa: SLF001


def test_dedup_and_fingerprint_counters_increment() -> None:
    new_before = DEDUP_MATCHES_TOTAL.labels(match_type="new")._value.get()  # noqa: SLF001
    suppressed_before = DEDUP_SUPPRESSED_TOTAL._value.get()  # noqa: SLF001
    hits_before = FINGERPRINT_HITS_TOTAL._value.get()  # noqa: SLF001
    errors_before = FINGERPRINT_ERRORS_TOTAL._value.get()  # noqa: SLF001

    increment_dedup_matches("new")
    increment_dedup_suppressed()
    increment_fingerprint_hits()
    increment_fingerprint_errors()

    assert DEDUP_MATCHES_TOTAL.labels(match_type="new")._value.get() == new_before + 1.0  # noqa: SLF001
    assert DEDUP_SUPPRESSED_TOTAL._value.get() == suppressed_before + 1.0  # noqa: SLF001
    assert FINGERPRINT_HITS_TOTAL._value.get() == hits_before + 1.0  # noqa: SLF001
    assert FINGERPRINT_ERRORS_TOTAL._value.get() == errors_before + 1.0  # noqa: SLF001


def test_increment_alerts_sent_uses_labels() -> None:
    before = ALERTS_SENT_TOTAL.labels(alert_type="first_seen", outcome="dry_run")._value.get()  # noqa: SLF001
    increment_alerts_sent("first_seen", "dry_run")
    after = ALERTS_SENT_TOTAL.labels(alert_type="first_seen", outcome="dry_run")._value.get()  # noqa: SLF001
    assert after == before + 1.0


def test_worker_metrics_use_worker_id_label() -> None:
    worker_id = "worker-test-1"
    claimed_before = WORKER_CHUNKS_CLAIMED_TOTAL.labels(worker_id=worker_id)._value.get()  # noqa: SLF001
    processed_before = WORKER_CHUNKS_PROCESSED_TOTAL.labels(worker_id=worker_id)._value.get()  # noqa: SLF001
    stale_before = WORKER_STALE_PROCESSING_RECOVERED_TOTAL.labels(worker_id=worker_id)._value.get()  # noqa: SLF001
    duplicate_before = WORKER_DUPLICATE_TRANSCRIPT_TOTAL.labels(worker_id=worker_id)._value.get()  # noqa: SLF001

    increment_worker_chunks_claimed(worker_id)
    increment_worker_chunks_processed(worker_id)
    increment_worker_stale_processing_recovered(worker_id, 2)
    increment_worker_duplicate_transcript(worker_id)

    assert WORKER_CHUNKS_CLAIMED_TOTAL.labels(worker_id=worker_id)._value.get() == claimed_before + 1.0  # noqa: SLF001
    assert WORKER_CHUNKS_PROCESSED_TOTAL.labels(worker_id=worker_id)._value.get() == processed_before + 1.0  # noqa: SLF001
    assert WORKER_STALE_PROCESSING_RECOVERED_TOTAL.labels(worker_id=worker_id)._value.get() == stale_before + 2.0  # noqa: SLF001
    assert WORKER_DUPLICATE_TRANSCRIPT_TOTAL.labels(worker_id=worker_id)._value.get() == duplicate_before + 1.0  # noqa: SLF001


def test_refresh_chunks_by_status_sets_gauges(tmp_path: Path) -> None:
    db_path = tmp_path / "metrics.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = conn.execute(
                "INSERT INTO stations (name, url, enabled) VALUES ('test-fm', 'http://x', 1)"
            ).lastrowid
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, 'a.wav', 1.0, 2.0, 'pending'), (?, 'b.wav', 2.0, 3.0, 'done')
                """,
                (station_id, station_id),
            )
    finally:
        conn.close()

    refresh_chunks_by_status(db_path)
    assert CHUNKS_BY_STATUS.labels(status="pending")._value.get() == 1.0  # noqa: SLF001
    assert CHUNKS_BY_STATUS.labels(status="done")._value.get() == 1.0  # noqa: SLF001
    assert CHUNKS_BY_STATUS.labels(status="processing")._value.get() == 0.0  # noqa: SLF001
