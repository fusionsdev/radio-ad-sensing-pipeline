"""Tests for WP-8 offset-tolerant chromaprint matching and known-ad annotation."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from shared.db import get_connection, migrate, transaction
from shared.models import PipelineSettings
from worker.fingerprint import (
    FingerprintAnnotator,
    FingerprintMatch,
    best_sliding_match,
    decode_fingerprint_vector,
    encode_fingerprint_vector,
)


class FakeFingerprintBackend:
    def __init__(self, vector: list[int]) -> None:
        self.vector = vector
        self.calls: list[Path] = []

    def compute(self, audio_path: Path) -> list[int]:
        self.calls.append(audio_path)
        return self.vector


def _make_vector(length: int, *, seed: int) -> list[int]:
    value = seed & 0xFFFFFFFF
    vector: list[int] = []
    for _ in range(length):
        value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
        vector.append(value)
    return vector


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "fingerprint.db"
    migrate(path)
    return path


@pytest.fixture
def settings() -> PipelineSettings:
    return PipelineSettings(same_station_airing_window_seconds=180)


def _seed_station(conn: sqlite3.Connection, name: str = "talk-a") -> int:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
        (name, f"https://example.com/{name}"),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_chunk(db_path: Path, tmp_path: Path, *, station_id: int, start_ts: float) -> tuple[int, Path]:
    audio = tmp_path / f"chunk-{int(start_ts)}.wav"
    audio.write_bytes(b"fake wav")
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (station_id, str(audio), start_ts, start_ts + 90.0),
            )
            chunk_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        conn.close()
    return chunk_id, audio


def _seed_canonical_with_fingerprint(db_path: Path, vector: list[int]) -> int:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO canonical_ads (company_name, phone_norm, category, first_seen, last_seen, airing_count)
                VALUES ('Rapid Capital', '8005551212', 'business_funding', 1000.0, 1000.0, 0)
                """
            )
            canonical_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                "INSERT INTO fingerprints (canonical_ad_id, chromaprint_vector, duration) VALUES (?, ?, ?)",
                (canonical_id, encode_fingerprint_vector(vector), 30.0),
            )
    finally:
        conn.close()
    return canonical_id


def test_encode_decode_fingerprint_vector_roundtrip_signed_ints() -> None:
    vector = [0, 1, -1, 2**31 - 1, -(2**31)]
    assert decode_fingerprint_vector(encode_fingerprint_vector(vector)) == vector


def test_best_sliding_match_finds_known_ad_at_offset() -> None:
    known = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
    chunk = [0x99999999, 0x88888888, *known, 0x77777777]

    match = best_sliding_match(
        chunk,
        [FingerprintMatch(candidate_id=42, vector=known, duration=30.0)],
        threshold=0.99,
        frames_per_second=4.0,
    )

    assert match is not None
    assert match.canonical_ad_id == 42
    assert match.offset_frames == 2
    assert match.offset_seconds == 0.5
    assert match.score == 1.0


def test_best_sliding_match_rejects_low_similarity() -> None:
    known = [0x00000000, 0x00000000, 0x00000000]
    chunk = [0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]

    assert best_sliding_match(
        chunk,
        [FingerprintMatch(candidate_id=7, vector=known, duration=20.0)],
        threshold=0.95,
    ) is None


def test_best_sliding_match_rejects_borderline_threshold_score() -> None:
    known = [0x00000000] * 25
    chunk = [*([0x00000000] * 22), 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]

    match = best_sliding_match(
        chunk,
        [FingerprintMatch(candidate_id=8, vector=known, duration=30.0)],
        threshold=0.88,
    )

    assert match is None


@pytest.mark.parametrize(
    ("offset_frames", "offset_seconds"),
    [
        (0, 0.0),
        (120, 30.0),
        (180, 45.0),
    ],
)
def test_best_sliding_match_finds_embedded_clip_at_realistic_offsets(
    offset_frames: int,
    offset_seconds: float,
) -> None:
    clip = _make_vector(120, seed=0xA11CE)
    chunk = _make_vector(360, seed=0xBEEF)
    chunk[offset_frames : offset_frames + len(clip)] = clip

    match = best_sliding_match(
        chunk,
        [FingerprintMatch(candidate_id=42, vector=clip, duration=30.0)],
        threshold=0.99,
        frames_per_second=4.0,
    )

    assert match is not None
    assert match.canonical_ad_id == 42
    assert match.offset_frames == offset_frames
    assert match.offset_seconds == offset_seconds
    assert match.score == 1.0


def test_best_sliding_match_stays_within_cpu_budget_for_100_candidates() -> None:
    clip = _make_vector(120, seed=0xC0FFEE)
    chunk = _make_vector(360, seed=0x12345678)
    chunk[180 : 180 + len(clip)] = clip
    candidates = [
        FingerprintMatch(candidate_id=index, vector=_make_vector(120, seed=0x1000 + index), duration=30.0)
        for index in range(99)
    ]
    candidates.append(FingerprintMatch(candidate_id=999, vector=clip, duration=30.0))

    started_at = time.perf_counter()
    match = best_sliding_match(
        chunk,
        candidates,
        threshold=0.99,
        frames_per_second=4.0,
    )
    elapsed = time.perf_counter() - started_at

    assert match is not None
    assert match.canonical_ad_id == 999
    assert elapsed < 1.0


def test_annotator_marks_known_ad_and_records_fast_path_detection(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    known = [10, 20, 30, 40]
    canonical_id = _seed_canonical_with_fingerprint(db_path, known)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
    finally:
        conn.close()
    chunk_id, audio = _seed_chunk(db_path, tmp_path, station_id=station_id, start_ts=2000.0)
    backend = FakeFingerprintBackend([1, 2, *known, 3, 4])
    annotator = FingerprintAnnotator(db_path, settings, backend=backend, threshold=0.99)

    match = annotator.annotate_chunk(chunk_id, audio)

    assert match is not None
    assert match.canonical_ad_id == canonical_id
    assert backend.calls == [audio]
    conn = get_connection(db_path)
    try:
        chunk = conn.execute("SELECT known_ad_id FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        assert chunk["known_ad_id"] == canonical_id
        detection = conn.execute("SELECT canonical_ad_id, is_ad FROM detections").fetchone()
        assert detection["canonical_ad_id"] == canonical_id
        assert detection["is_ad"] == 1
        canonical = conn.execute("SELECT airing_count, last_seen FROM canonical_ads WHERE id = ?", (canonical_id,)).fetchone()
        assert canonical["airing_count"] == 1
        assert canonical["last_seen"] == 2000.0
    finally:
        conn.close()


def test_known_ad_inside_same_station_window_does_not_increment_airing_count(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    known = [10, 20, 30, 40]
    canonical_id = _seed_canonical_with_fingerprint(db_path, known)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
    finally:
        conn.close()
    previous_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_id=station_id, start_ts=2000.0)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO detections (chunk_id, canonical_ad_id, is_ad) VALUES (?, ?, 1)",
                (previous_chunk_id, canonical_id),
            )
            conn.execute("UPDATE canonical_ads SET airing_count = 1 WHERE id = ?", (canonical_id,))
    finally:
        conn.close()
    chunk_id, audio = _seed_chunk(db_path, tmp_path, station_id=station_id, start_ts=2060.0)
    annotator = FingerprintAnnotator(db_path, settings, backend=FakeFingerprintBackend([*known]), threshold=0.99)

    assert annotator.annotate_chunk(chunk_id, audio) is not None

    conn = get_connection(db_path)
    try:
        assert conn.execute("SELECT airing_count FROM canonical_ads WHERE id = ?", (canonical_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM detections WHERE canonical_ad_id = ?", (canonical_id,)).fetchone()[0] == 2
    finally:
        conn.close()
