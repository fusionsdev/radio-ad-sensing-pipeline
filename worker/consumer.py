"""SQLite-backed chunk queue consumer with drop-oldest policy."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from shared.config import load_loan_keywords
from shared.db import get_connection, retry_on_busy, transaction
from shared.metrics import (
    increment_chunks_dropped,
    increment_chunks_processed,
    increment_fingerprint_errors,
    increment_fingerprint_hits,
    observe_asr_metrics,
    observe_llm_extraction_duration,
    observe_stage_duration,
    refresh_chunks_by_status,
    set_asr_rtf_avg,
    set_queue_pending_hours,
)
from shared.models import AdExtraction, ChunkStatus, LoanKeywordEntry, PipelineSettings
from worker.dedup import DetectionPersister
from worker.extract import OllamaExtractor
from worker.fingerprint import FingerprintAnnotator, FingerprintMatch
from worker.janitor import ChunkJanitor
from shared.verticals import keyword_to_vertical_map, load_vertical_keywords
from worker.advertiser_intel import extract_advertiser_intel, record_advertiser_opportunity
from worker.keywords import KeywordMatch, find_keyword_matches, record_keyword_hits
from worker.transcribe import Transcriber, TranscriptionResult, WhisperBackend

logger = logging.getLogger("worker")

JANITOR_SWEEP_INTERVAL = 60

CLAIM_SQL = """
UPDATE chunks
SET status = 'processing'
WHERE id = (
    SELECT id FROM chunks
    WHERE status = 'pending'
    ORDER BY start_ts
    LIMIT 1
)
RETURNING id, station_id, path, start_ts, end_ts
"""


@dataclass(frozen=True)
class ClaimedChunk:
    id: int
    station_id: int
    station: str
    path: str
    start_ts: float
    end_ts: float

    @property
    def audio_duration_sec(self) -> float:
        return self.end_ts - self.start_ts


class ExtractionBackend(Protocol):
    def extract(self, transcript_text: str) -> AdExtraction: ...


class DetectionPersistenceBackend(Protocol):
    def record_extraction(
        self,
        chunk_id: int,
        extraction: AdExtraction,
        *,
        transcript_text: str,
        segments: list[Any],
    ) -> int | None: ...


class FingerprintAnnotationBackend(Protocol):
    def annotate_chunk(self, chunk_id: int, audio_path: Path) -> FingerprintMatch | None: ...


class ChunkConsumer:
    """Poll pending chunks, transcribe, persist transcripts, enforce backlog cap."""

    def __init__(
        self,
        db_path: str | Path,
        settings: PipelineSettings,
        transcriber: WhisperBackend,
        *,
        extractor: ExtractionBackend | None = None,
        detection_persister: DetectionPersistenceBackend | None = None,
        fingerprint_annotator: FingerprintAnnotationBackend | None = None,
        janitor: ChunkJanitor | None = None,
        poll_interval_sec: float = 1.0,
        loan_keywords: list[LoanKeywordEntry] | list[str] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.settings = settings
        self.transcriber = transcriber
        self.extractor = extractor
        self.detection_persister = detection_persister
        self.fingerprint_annotator = fingerprint_annotator
        self.janitor = janitor if janitor is not None else ChunkJanitor(db_path, settings)
        self.poll_interval_sec = poll_interval_sec
        self.loan_keywords = loan_keywords if loan_keywords is not None else load_loan_keywords()
        self._run_loops = 0

    def run(self, stop_event: Any | None = None) -> None:
        """Poll until stop_event is set."""
        self._reclaim_orphaned_processing()
        while stop_event is None or not stop_event.is_set():
            processed = self.run_once()
            self._run_loops += 1
            if self.janitor is not None and self._run_loops % JANITOR_SWEEP_INTERVAL == 0:
                self.janitor.run_sweep()
            if not processed:
                if stop_event is not None and stop_event.wait(self.poll_interval_sec):
                    break
                elif stop_event is None:
                    time.sleep(self.poll_interval_sec)
            elif stop_event is not None and stop_event.is_set():
                break

    @retry_on_busy()
    def _reclaim_orphaned_processing(self) -> int:
        """Requeue chunks stuck in 'processing' from a previous crash.

        A chunk is set to 'processing' before transcription, which runs outside
        that transaction; a crash/OOM/restart mid-chunk leaves the row stuck
        forever because the claim query only selects 'pending'. The pipeline runs
        a single worker process, so at startup any 'processing' row is necessarily
        an orphan and safe to requeue. Without this, every crash silently leaks a
        chunk (and its audio is later swept), losing the detection permanently.
        """
        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                cursor = conn.execute(
                    """
                    UPDATE chunks
                    SET status = 'pending',
                        error = 'requeued_orphaned_processing'
                    WHERE status = 'processing'
                    """
                )
                reclaimed = cursor.rowcount
        finally:
            conn.close()
        if reclaimed:
            logger.warning("reclaimed orphaned processing chunks", extra={"count": reclaimed})
        return reclaimed

    @retry_on_busy()
    def run_once(self) -> bool:
        """Process one chunk if available. Returns True when work was done."""
        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                self._enforce_drop_oldest(conn)
                chunk = self._claim_chunk(conn)
                if chunk is None:
                    return False

            processed = self._process_claimed(chunk)
            if processed:
                increment_chunks_processed("worker")
            return processed
        finally:
            conn.close()
            set_queue_pending_hours(self.db_path)
            refresh_chunks_by_status(self.db_path)

    def _enforce_drop_oldest(self, conn: sqlite3.Connection) -> None:
        max_seconds = self.settings.queue_max_hours * 3600
        rows = conn.execute(
            """
            SELECT id, station_id, start_ts, end_ts
            FROM chunks
            WHERE status = 'pending'
            ORDER BY start_ts ASC
            """
        ).fetchall()
        if not rows:
            return

        total_duration = sum(row["end_ts"] - row["start_ts"] for row in rows)
        if total_duration <= max_seconds:
            return

        need_to_drop = total_duration - max_seconds
        drop_rows: list[sqlite3.Row] = []
        accumulated = 0.0
        for row in rows:
            drop_rows.append(row)
            accumulated += row["end_ts"] - row["start_ts"]
            if accumulated >= need_to_drop:
                break

        drop_ids = [row["id"] for row in drop_rows]
        placeholders = ",".join("?" * len(drop_ids))
        conn.execute(
            f"""
            UPDATE chunks
            SET status = 'dropped', error = 'dropped_backlog'
            WHERE id IN ({placeholders})
            """,
            drop_ids,
        )
        increment_chunks_dropped(len(drop_ids))
        self._insert_backlog_gaps(conn, drop_rows)
        logger.warning(
            "dropped backlog overflow",
            extra={
                "dropped_count": len(drop_ids),
                "overflow_seconds": need_to_drop,
            },
        )

    def _insert_backlog_gaps(
        self,
        conn: sqlite3.Connection,
        dropped_rows: list[sqlite3.Row],
    ) -> None:
        by_station: dict[int, list[sqlite3.Row]] = {}
        for row in dropped_rows:
            by_station.setdefault(row["station_id"], []).append(row)

        now = time.time()
        for station_id, station_rows in by_station.items():
            station_rows.sort(key=lambda r: r["start_ts"])
            for start_ts, end_ts in _merge_contiguous_ranges(station_rows):
                conn.execute(
                    """
                    INSERT INTO gaps (station_id, start_ts, end_ts, reason)
                    VALUES (?, ?, ?, 'dropped_backlog')
                    """,
                    (station_id, start_ts, end_ts),
                )

    def _claim_chunk(self, conn: sqlite3.Connection) -> ClaimedChunk | None:
        row = conn.execute(CLAIM_SQL).fetchone()
        if row is None:
            return None
        station_row = conn.execute(
            "SELECT name FROM stations WHERE id = ?",
            (row["station_id"],),
        ).fetchone()
        station_name = str(station_row["name"]) if station_row is not None else str(row["station_id"])
        return ClaimedChunk(
            id=row["id"],
            station_id=row["station_id"],
            station=station_name,
            path=row["path"],
            start_ts=row["start_ts"],
            end_ts=row["end_ts"],
        )

    def _resolve_audio_path(self, raw_path: str) -> Path:
        """Resolve chunk paths written by Windows/MSYS or Linux containers.

        Older ingestor builds wrote paths like ``data\\chunks\\station\\file.wav``.
        Inside the Linux worker container, backslashes are literal characters, not
        path separators, so ``Path(raw_path).is_file()`` falsely reports missing
        audio. Prefer the current Linux path and fall back to legacy-normalized
        forms so queued chunks survive image/config upgrades.
        """
        normalized = raw_path.replace("\\", "/")
        candidates = [Path(normalized)]
        if normalized.startswith("data/chunks/"):
            candidates.append(Path("/app/chunks") / normalized.removeprefix("data/chunks/"))
        elif not normalized.startswith("/"):
            candidates.append(Path("/app") / normalized)

        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    def _process_claimed(self, chunk: ClaimedChunk) -> bool:
        # Only delete the source WAV once the chunk is genuinely done. Deleting on
        # transcription/extraction failure makes the lost ad unrecoverable, so keep
        # the audio on any failure path and let retention/reprocessing handle it.
        delete_path: Path | None = None
        try:
            audio_path = self._resolve_audio_path(chunk.path)
            if not audio_path.is_file():
                self._mark_dropped(chunk.id, f"missing audio file: {chunk.path}")
                return True

            known_ad_match: FingerprintMatch | None = None
            if self.fingerprint_annotator is not None:
                fingerprint_started = time.perf_counter()
                try:
                    known_ad_match = self.fingerprint_annotator.annotate_chunk(chunk.id, audio_path)
                except Exception:
                    increment_fingerprint_errors()
                    logger.exception(
                        "fingerprint annotation failed; continuing with ASR/LLM path",
                        extra={"chunk_id": chunk.id, "path": chunk.path},
                    )
                finally:
                    observe_stage_duration(
                        "fingerprint",
                        time.perf_counter() - fingerprint_started,
                    )

            if known_ad_match is not None:
                increment_fingerprint_hits()

            try:
                result = self.transcriber.transcribe(
                    audio_path,
                    audio_duration_sec=chunk.audio_duration_sec,
                )
            except Exception as exc:
                logger.exception(
                    "transcription failed",
                    extra={"chunk_id": chunk.id, "path": chunk.path},
                )
                self._mark_dropped(chunk.id, str(exc))
                return True

            observe_stage_duration("asr", result.wall_time_sec)
            observe_asr_metrics(chunk.station, result.wall_time_sec, result.rtf)

            self._persist_success(chunk, result)
            extraction_ok = True
            if (
                known_ad_match is None
                and self.extractor is not None
                and self.detection_persister is not None
            ):
                try:
                    llm_started = time.perf_counter()
                    extraction = self.extractor.extract(result.text)
                    llm_duration_sec = time.perf_counter() - llm_started
                    observe_llm_extraction_duration(llm_duration_sec)
                    observe_stage_duration("llm", llm_duration_sec)

                    dedup_started = time.perf_counter()
                    self.detection_persister.record_extraction(
                        chunk.id,
                        extraction,
                        transcript_text=result.text,
                        segments=result.segments,
                    )
                    observe_stage_duration(
                        "dedup",
                        time.perf_counter() - dedup_started,
                    )
                except Exception as exc:
                    logger.exception(
                        "extraction/dedup failed",
                        extra={"chunk_id": chunk.id, "path": chunk.path},
                    )
                    self._mark_dropped(chunk.id, f"extraction/dedup failed: {exc}")
                    extraction_ok = False
            if extraction_ok:
                # Chunk is fully processed (status='done'); safe to reclaim disk.
                delete_path = audio_path
            return True
        finally:
            if self.janitor is not None and delete_path is not None:
                self.janitor.delete_after_processing(delete_path)

    @retry_on_busy()
    def _persist_success(self, chunk: ClaimedChunk, result: TranscriptionResult) -> None:
        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                segments_json = json.dumps(
                    [
                        {"start": s.start, "end": s.end, "text": s.text}
                        for s in result.segments
                    ]
                )
                conn.execute(
                    """
                    INSERT INTO transcripts (chunk_id, text, asr_duration_ms, segments_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        result.text,
                        int(result.wall_time_sec * 1000),
                        segments_json,
                    ),
                )
                conn.execute(
                    "UPDATE chunks SET status = 'done', error = NULL WHERE id = ?",
                    (chunk.id,),
                )
                if self.loan_keywords:
                    matches = find_keyword_matches(
                        result.text,
                        self.loan_keywords,
                        min_record_confidence=float(self.settings.keyword_min_record_confidence),
                    )
                    if matches:
                        record_keyword_hits(
                            conn,
                            station_id=chunk.station_id,
                            chunk_id=chunk.id,
                            hit_ts=chunk.start_ts,
                            matches=matches,
                        )
                        self._extract_advertiser_opportunities(
                            conn,
                            chunk=chunk,
                            transcript=result.text,
                            matches=matches,
                        )
                self._update_rtf_avg(conn, result.rtf)
                set_asr_rtf_avg(result.rtf)
        finally:
            conn.close()

        logger.info(
            "chunk transcribed",
            extra={
                "chunk_id": chunk.id,
                "rtf": result.rtf,
                "asr_wall_time_sec": result.wall_time_sec,
                "chunk_audio_duration_sec": result.audio_duration_sec,
            },
        )

    @retry_on_busy()
    def _mark_dropped(self, chunk_id: int, error: str) -> None:
        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                conn.execute(
                    """
                    UPDATE chunks
                    SET status = 'dropped', error = ?
                    WHERE id = ?
                    """,
                    (error, chunk_id),
                )
        finally:
            conn.close()
        increment_chunks_dropped()
        logger.warning(
            "chunk dropped",
            extra={"chunk_id": chunk_id, "error": error},
        )

    def _extract_advertiser_opportunities(
        self,
        conn: sqlite3.Connection,
        *,
        chunk: ClaimedChunk,
        transcript: str,
        matches: list[KeywordMatch],
    ) -> None:
        vertical_config = load_vertical_keywords()
        kw_vertical = keyword_to_vertical_map(vertical_config)
        extract_verticals = {
            vid
            for vid, vertical in vertical_config.verticals.items()
            if vertical.extract_advertisers
        }
        if not extract_verticals:
            return

        by_vertical: dict[str, list[str]] = {}
        for match in matches:
            vertical_id = kw_vertical.get(match.keyword.lower())
            if vertical_id in extract_verticals:
                by_vertical.setdefault(vertical_id, []).append(match.keyword)

        if not by_vertical:
            return

        detection = conn.execute(
            """
            SELECT company_name, phone_number, website, offer_summary, confidence
            FROM detections
            WHERE chunk_id = ? AND is_ad = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (chunk.id,),
        ).fetchone()

        for vertical_id, keywords in by_vertical.items():
            intel = extract_advertiser_intel(
                transcript=transcript,
                source_keywords=keywords,
                detection_row=detection,
            )
            record_advertiser_opportunity(
                conn,
                vertical=vertical_id,
                station_id=chunk.station_id,
                chunk_id=chunk.id,
                keyword_hit_id=None,
                hit_ts=chunk.start_ts,
                source_keywords=keywords,
                audio_clip_path=chunk.path,
                intel=intel,
            )

    def _update_rtf_avg(self, conn: sqlite3.Connection, rtf: float) -> None:
        now = time.time()
        count_row = conn.execute(
            "SELECT value FROM status WHERE key = 'asr_rtf_count'"
        ).fetchone()
        avg_row = conn.execute(
            "SELECT value FROM status WHERE key = 'asr_rtf_avg'"
        ).fetchone()

        count = int(count_row["value"]) if count_row else 0
        if avg_row:
            old_avg = float(avg_row["value"])
            new_avg = (old_avg * count + rtf) / (count + 1)
        else:
            new_avg = rtf
        new_count = count + 1

        conn.execute(
            """
            INSERT INTO status (key, value, updated_at) VALUES ('asr_rtf_avg', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (str(new_avg), now),
        )
        conn.execute(
            """
            INSERT INTO status (key, value, updated_at) VALUES ('asr_rtf_count', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (str(new_count), now),
        )


def _merge_contiguous_ranges(
    rows: list[sqlite3.Row],
) -> list[tuple[float, float]]:
    """Merge dropped chunks into station-local contiguous time ranges."""
    ranges: list[tuple[float, float]] = []
    current_start: float | None = None
    current_end: float | None = None

    for row in rows:
        start_ts = row["start_ts"]
        end_ts = row["end_ts"]
        if current_start is None:
            current_start = start_ts
            current_end = end_ts
        elif start_ts <= current_end + 1.0:
            current_end = max(current_end, end_ts)
        else:
            ranges.append((current_start, current_end))
            current_start = start_ts
            current_end = end_ts

    if current_start is not None and current_end is not None:
        ranges.append((current_start, current_end))
    return ranges


def create_consumer(
    db_path: str | Path,
    settings: PipelineSettings,
    *,
    transcriber: WhisperBackend | None = None,
    extractor: ExtractionBackend | None = None,
    detection_persister: DetectionPersistenceBackend | None = None,
    fingerprint_annotator: FingerprintAnnotationBackend | None = None,
    poll_interval_sec: float = 1.0,
) -> ChunkConsumer:
    """Factory for production consumer with default ASR, extraction, dedup, and fingerprint backends."""
    backend = transcriber or Transcriber(settings)
    extraction_backend = extractor or OllamaExtractor()
    persister = detection_persister or DetectionPersister(db_path, settings)
    annotator = fingerprint_annotator or FingerprintAnnotator(db_path, settings)
    return ChunkConsumer(
        db_path,
        settings,
        backend,
        extractor=extraction_backend,
        detection_persister=persister,
        fingerprint_annotator=annotator,
        poll_interval_sec=poll_interval_sec,
    )
