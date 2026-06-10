"""WP-8 chromaprint computation and offset-tolerant known-ad annotation."""

from __future__ import annotations

import json
import sqlite3
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from shared.db import get_connection, retry_on_busy, transaction
from shared.models import PipelineSettings

DEFAULT_FRAMES_PER_SECOND = 4.0


class FingerprintBackend(Protocol):
    def compute(self, audio_path: Path) -> list[int]: ...


@dataclass(frozen=True)
class FingerprintMatch:
    """Candidate fingerprint plus the best offset/score after matching."""

    candidate_id: int
    vector: list[int]
    duration: float
    score: float = 0.0
    offset_frames: int = 0
    offset_seconds: float = 0.0

    @property
    def canonical_ad_id(self) -> int:
        return self.candidate_id


def encode_fingerprint_vector(vector: list[int]) -> bytes:
    """Encode signed 32-bit chromaprint feature integers for SQLite BLOB storage."""
    if not vector:
        return b""
    return struct.pack(f"<{len(vector)}i", *vector)


def decode_fingerprint_vector(blob: bytes) -> list[int]:
    """Decode signed 32-bit chromaprint feature integers from SQLite BLOB storage."""
    if not blob:
        return []
    if len(blob) % 4 != 0:
        raise ValueError("fingerprint blob length must be divisible by 4")
    return list(struct.unpack(f"<{len(blob) // 4}i", blob))


def _frame_similarity(left: int, right: int) -> float:
    xor = (left ^ right) & 0xFFFFFFFF
    return 1.0 - (xor.bit_count() / 32.0)


def _window_similarity(chunk_window: list[int], candidate: list[int]) -> float:
    if not chunk_window or len(chunk_window) != len(candidate):
        return 0.0
    return sum(_frame_similarity(left, right) for left, right in zip(chunk_window, candidate, strict=True)) / len(candidate)


def best_sliding_match(
    chunk_vector: list[int],
    candidates: list[FingerprintMatch],
    *,
    threshold: float = 0.88,
    frames_per_second: float = DEFAULT_FRAMES_PER_SECOND,
) -> FingerprintMatch | None:
    """Find the best offset-tolerant match for an ad fingerprint inside a larger chunk."""
    best: FingerprintMatch | None = None
    for candidate in candidates:
        needle = candidate.vector
        if not needle or len(needle) > len(chunk_vector):
            continue
        for offset in range(0, len(chunk_vector) - len(needle) + 1):
            window = chunk_vector[offset : offset + len(needle)]
            score = _window_similarity(window, needle)
            if best is None or score > best.score:
                best = FingerprintMatch(
                    candidate_id=candidate.candidate_id,
                    vector=needle,
                    duration=candidate.duration,
                    score=score,
                    offset_frames=offset,
                    offset_seconds=offset / frames_per_second if frames_per_second else 0.0,
                )
    if best is None or best.score <= threshold:
        return None
    return best


class FpcalcBackend:
    """Compute raw chromaprint vectors with the fpcalc CLI."""

    def compute(self, audio_path: Path) -> list[int]:
        command = ["fpcalc", "-raw", "-json", str(audio_path)]
        result = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
        data = json.loads(result.stdout)
        fingerprint = data.get("fingerprint")
        if not isinstance(fingerprint, list):
            raise ValueError("fpcalc JSON did not contain a raw fingerprint list")
        return [int(item) for item in fingerprint]


class FingerprintAnnotator:
    """Compute a chunk fingerprint, match against canonical ads, and record known-ad airings."""

    def __init__(
        self,
        db_path: str | Path,
        settings: PipelineSettings,
        *,
        backend: FingerprintBackend | None = None,
        threshold: float = 0.88,
        frames_per_second: float = DEFAULT_FRAMES_PER_SECOND,
    ) -> None:
        self.db_path = Path(db_path)
        self.settings = settings
        self.backend = backend or FpcalcBackend()
        self.threshold = threshold
        self.frames_per_second = frames_per_second

    @retry_on_busy(max_retries=8, base_delay=0.01)
    def annotate_chunk(self, chunk_id: int, audio_path: Path) -> FingerprintMatch | None:
        chunk_vector = self.backend.compute(audio_path)
        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                candidates = self._load_candidates(conn)
                match = best_sliding_match(
                    chunk_vector,
                    candidates,
                    threshold=self.threshold,
                    frames_per_second=self.frames_per_second,
                )
                if match is None:
                    return None
                chunk = self._chunk_row(conn, chunk_id)
                self._record_known_ad(conn, chunk, match.canonical_ad_id)
                return match
        finally:
            conn.close()

    def add_fingerprint_for_canonical(self, canonical_ad_id: int, audio_path: Path, *, duration: float) -> int:
        """Compute and store a fingerprint for a newly archived canonical ad clip."""
        vector = self.backend.compute(audio_path)
        conn = get_connection(self.db_path)
        try:
            with transaction(conn):
                conn.execute(
                    "INSERT INTO fingerprints (canonical_ad_id, chromaprint_vector, duration) VALUES (?, ?, ?)",
                    (canonical_ad_id, encode_fingerprint_vector(vector), duration),
                )
                return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        finally:
            conn.close()

    def _load_candidates(self, conn: sqlite3.Connection) -> list[FingerprintMatch]:
        rows = conn.execute(
            "SELECT canonical_ad_id, chromaprint_vector, duration FROM fingerprints"
        ).fetchall()
        return [
            FingerprintMatch(
                candidate_id=int(row["canonical_ad_id"]),
                vector=decode_fingerprint_vector(row["chromaprint_vector"]),
                duration=float(row["duration"]),
            )
            for row in rows
        ]

    def _chunk_row(self, conn: sqlite3.Connection, chunk_id: int) -> sqlite3.Row:
        row = conn.execute(
            "SELECT id, station_id, start_ts FROM chunks WHERE id = ?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"chunk not found: {chunk_id}")
        return row

    def _record_known_ad(self, conn: sqlite3.Connection, chunk: sqlite3.Row, canonical_ad_id: int) -> None:
        duplicate_airing = self._has_recent_same_station_airing(conn, canonical_ad_id, chunk)
        canonical = conn.execute(
            "SELECT company_name, phone_norm, category FROM canonical_ads WHERE id = ?",
            (canonical_ad_id,),
        ).fetchone()
        if canonical is None:
            raise ValueError(f"canonical ad not found: {canonical_ad_id}")

        conn.execute(
            "UPDATE chunks SET known_ad_id = ? WHERE id = ?",
            (canonical_ad_id, chunk["id"]),
        )
        conn.execute(
            """
            INSERT INTO detections (
                chunk_id, canonical_ad_id, is_ad, ad_category, company_name, phone_number,
                offer_summary, key_claims, confidence, alerted
            )
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                chunk["id"],
                canonical_ad_id,
                canonical["category"],
                canonical["company_name"],
                canonical["phone_norm"],
                "known ad matched by chromaprint",
                json.dumps([]),
                1.0,
            ),
        )
        increment = 0 if duplicate_airing else 1
        conn.execute(
            """
            UPDATE canonical_ads
            SET last_seen = MAX(last_seen, ?), airing_count = airing_count + ?
            WHERE id = ?
            """,
            (chunk["start_ts"], increment, canonical_ad_id),
        )

    def _has_recent_same_station_airing(
        self,
        conn: sqlite3.Connection,
        canonical_ad_id: int,
        chunk: sqlite3.Row,
    ) -> bool:
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
            (
                canonical_ad_id,
                chunk["station_id"],
                chunk["start_ts"],
                self.settings.same_station_airing_window_seconds,
            ),
        ).fetchone()
        return row is not None
