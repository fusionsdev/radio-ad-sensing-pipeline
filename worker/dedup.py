"""WP-5 fuzzy deduplication, persistence, and ad clip archiving."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from shared.db import get_connection, retry_on_busy, transaction
from shared.metrics import (
    increment_dedup_matches,
    increment_dedup_suppressed,
    increment_detections,
)
from shared.models import AdExtraction, PipelineSettings
from worker.extract import normalize_phone_number
from worker.transcribe import TranscriptSegment

try:  # pragma: no cover - fallback only when dev dependency is absent
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    class _FuzzFallback:
        @staticmethod
        def token_set_ratio(left: str, right: str) -> int:
            left_tokens = " ".join(sorted(set(left.lower().split())))
            right_tokens = " ".join(sorted(set(right.lower().split())))
            return int(SequenceMatcher(None, left_tokens, right_tokens).ratio() * 100)

    fuzz = _FuzzFallback()  # type: ignore[assignment]

Clipper = Callable[[Path, Path, float, float], Path]


def _norm_text(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _token_overlap_score(segment_text: str, needles: Sequence[str]) -> int:
    segment = _norm_text(segment_text)
    if not segment:
        return 0
    score = 0
    for needle in needles:
        n = _norm_text(needle)
        if not n:
            continue
        if n in segment:
            score += 4
            continue
        ratio = fuzz.token_set_ratio(segment, n)
        if ratio >= 80:
            score += 3
        elif ratio >= 60:
            score += 1
    return score


def estimate_ad_bounds(
    segments: Sequence[TranscriptSegment],
    extraction: AdExtraction,
    *,
    chunk_duration_sec: float,
    padding_sec: float = 2.0,
) -> tuple[float, float]:
    """Estimate clip bounds by mapping extracted ad fields back to Whisper segments."""
    if not segments:
        return 0.0, max(0.0, chunk_duration_sec)

    needles: list[str] = []
    for value in (extraction.company_name, extraction.offer_summary, extraction.website, extraction.phone_number):
        if value:
            needles.append(value)
    needles.extend(extraction.key_claims)

    matched = [segment for segment in segments if _token_overlap_score(segment.text, needles) > 0]
    if not matched:
        return 0.0, max(0.0, chunk_duration_sec)

    start = max(0.0, min(segment.start for segment in matched) - padding_sec)
    end = min(max(0.0, chunk_duration_sec), max(segment.end for segment in matched) + padding_sec)
    if end <= start:
        return 0.0, max(0.0, chunk_duration_sec)
    return start, end


def ffmpeg_clip(source: Path, dest: Path, start_sec: float, end_sec: float) -> Path:
    """Cut a clip with ffmpeg; copy the file as a safe fallback in dev/test environments."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, end_sec - start_sec)
    if shutil.which("ffmpeg"):
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            str(dest),
        ]
        try:
            subprocess.run(command, check=True)  # noqa: S603 - args are fixed and not shell-expanded
            return dest
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    if source.is_file():
        shutil.copyfile(source, dest)
    else:
        dest.write_bytes(b"")
    return dest


class DetectionPersister:
    """Persist validated extraction output and attach it to a canonical ad."""

    def __init__(
        self,
        db_path: str | Path,
        settings: PipelineSettings,
        *,
        archive_dir: str | Path = "data/ad_archive",
        clipper: Clipper = ffmpeg_clip,
    ) -> None:
        self.db_path = Path(db_path)
        self.settings = settings
        self.archive_dir = Path(archive_dir)
        self.clipper = clipper

    @retry_on_busy(max_retries=8, base_delay=0.01)
    def record_extraction(
        self,
        chunk_id: int,
        extraction: AdExtraction,
        *,
        transcript_text: str,
        segments: Sequence[TranscriptSegment],
    ) -> int | None:
        """Record an ad extraction; returns detection id, or None for non-alertable output."""
        confidence = extraction.confidence or 0.0
        if not extraction.is_ad or confidence < self.settings.confidence_threshold:
            return None

        phone_norm = normalize_phone_number(extraction.phone_number)
        if phone_norm != extraction.phone_number:
            extraction = extraction.model_copy(update={"phone_number": phone_norm})

        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                chunk = self._chunk_row(conn, chunk_id)
                canonical_id = self._find_matching_canonical(conn, extraction, transcript_text, chunk["start_ts"])
                if canonical_id is None:
                    canonical_id = self._create_canonical(conn, extraction, chunk, segments)
                    increment_dedup_matches("new")
                else:
                    increment_dedup_matches("existing")

                duplicate_airing = self._has_recent_same_station_airing(conn, canonical_id, chunk)
                detection_id = self._insert_detection(conn, chunk_id, canonical_id, extraction)
                increment = 0 if duplicate_airing else 1
                conn.execute(
                    """
                    UPDATE canonical_ads
                    SET last_seen = MAX(last_seen, ?), airing_count = airing_count + ?
                    WHERE id = ?
                    """,
                    (chunk["start_ts"], increment, canonical_id),
                )
                if duplicate_airing:
                    increment_dedup_suppressed()
                increment_detections()
                return detection_id
        finally:
            conn.close()

    def _chunk_row(self, conn: sqlite3.Connection, chunk_id: int) -> sqlite3.Row:
        row = conn.execute(
            "SELECT id, station_id, path, start_ts, end_ts FROM chunks WHERE id = ?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"chunk not found: {chunk_id}")
        return row

    def _find_matching_canonical(
        self,
        conn: sqlite3.Connection,
        extraction: AdExtraction,
        transcript_text: str,
        now_ts: float,
    ) -> int | None:
        cutoff = now_ts - (self.settings.dedup_window_days * 86400)
        rows = conn.execute(
            """
            SELECT c.*, d.offer_summary, d.key_claims
            FROM canonical_ads c
            LEFT JOIN detections d ON d.id = (
                SELECT id FROM detections
                WHERE canonical_ad_id = c.id
                ORDER BY id DESC
                LIMIT 1
            )
            WHERE c.last_seen >= ?
            """,
            (cutoff,),
        ).fetchall()

        best_id: int | None = None
        best_score = -1.0
        for row in rows:
            score = self._canonical_score(row, extraction, transcript_text)
            if score > best_score:
                best_score = score
                best_id = int(row["id"])
        if best_score >= self.settings.fuzzy_match_threshold:
            return best_id
        return None

    def _canonical_score(self, row: sqlite3.Row, extraction: AdExtraction, transcript_text: str) -> float:
        scores: list[float] = []
        weights: list[float] = []

        existing_phone = row["phone_norm"]
        new_phone = normalize_phone_number(extraction.phone_number)
        if existing_phone and new_phone:
            if existing_phone == new_phone:
                scores.append(100.0)
                weights.append(3.0)

        if row["company_name"] and extraction.company_name:
            scores.append(float(fuzz.token_set_ratio(row["company_name"], extraction.company_name)))
            weights.append(2.5)

        if row["category"] and extraction.ad_category:
            scores.append(100.0 if _norm_text(row["category"]) == _norm_text(extraction.ad_category) else 0.0)
            weights.append(1.0)

        prior_summary = row["offer_summary"] or ""
        new_offer = extraction.offer_summary or ""
        if prior_summary and (new_offer or transcript_text):
            # Compare offer-to-offer; only fall back to the raw transcript when the
            # new extraction has no offer summary. Concatenating the full transcript
            # floods the token set and makes the offer score nearly meaningless.
            comparison = new_offer or transcript_text
            scores.append(float(fuzz.token_set_ratio(prior_summary, comparison)))
            weights.append(1.0)

        if not scores:
            return 0.0
        return sum(score * weight for score, weight in zip(scores, weights, strict=True)) / sum(weights)

    def _create_canonical(
        self,
        conn: sqlite3.Connection,
        extraction: AdExtraction,
        chunk: sqlite3.Row,
        segments: Sequence[TranscriptSegment],
    ) -> int:
        conn.execute(
            """
            INSERT INTO canonical_ads (company_name, phone_norm, category, first_seen, last_seen, airing_count)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                extraction.company_name,
                normalize_phone_number(extraction.phone_number),
                extraction.ad_category,
                chunk["start_ts"],
                chunk["start_ts"],
            ),
        )
        canonical_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        source = Path(chunk["path"])
        duration = max(0.0, float(chunk["end_ts"] - chunk["start_ts"]))
        start_sec, end_sec = estimate_ad_bounds(segments, extraction, chunk_duration_sec=duration)
        archive_path = self.archive_dir / f"canonical_ad_{canonical_id}.wav"
        clipped = self.clipper(source, archive_path, start_sec, end_sec)
        conn.execute(
            "UPDATE canonical_ads SET archived_audio_path = ? WHERE id = ?",
            (str(clipped), canonical_id),
        )
        return canonical_id

    def _has_recent_same_station_airing(
        self,
        conn: sqlite3.Connection,
        canonical_id: int,
        chunk: sqlite3.Row,
    ) -> bool:
        window = self.settings.same_station_airing_window_seconds
        row = conn.execute(
            """
            SELECT 1
            FROM detections d
            JOIN chunks c ON c.id = d.chunk_id
            WHERE d.canonical_ad_id = ?
              AND c.station_id = ?
              AND ABS(c.start_ts - ?) <= ?
            LIMIT 1
            """,
            (canonical_id, chunk["station_id"], chunk["start_ts"], window),
        ).fetchone()
        return row is not None

    def _insert_detection(
        self,
        conn: sqlite3.Connection,
        chunk_id: int,
        canonical_id: int,
        extraction: AdExtraction,
    ) -> int:
        conn.execute(
            """
            INSERT INTO detections (
                chunk_id, canonical_ad_id, is_ad, ad_category, company_name, phone_number,
                website, offer_summary, key_claims, confidence, alerted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                chunk_id,
                canonical_id,
                1 if extraction.is_ad else 0,
                extraction.ad_category,
                extraction.company_name,
                extraction.phone_number,
                extraction.website,
                extraction.offer_summary,
                json.dumps(extraction.key_claims),
                extraction.confidence,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
