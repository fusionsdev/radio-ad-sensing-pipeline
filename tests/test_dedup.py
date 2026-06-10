"""Tests for WP-5 fuzzy deduplication, persistence, and clip archiving."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from shared.db import get_connection, migrate, transaction
from shared.models import AdExtraction, PipelineSettings
from worker.dedup import DetectionPersister, estimate_ad_bounds
from worker.transcribe import TranscriptSegment


class FakeClipper:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path, float, float]] = []

    def __call__(self, source: Path, dest: Path, start_sec: float, end_sec: float) -> Path:
        self.calls.append((source, dest, start_sec, end_sec))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"clip")
        return dest


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "dedup.db"
    migrate(path)
    return path


@pytest.fixture
def settings() -> PipelineSettings:
    return PipelineSettings(
        fuzzy_match_threshold=85,
        dedup_window_days=7,
        same_station_airing_window_seconds=180,
        confidence_threshold=0.7,
    )


def _seed_station(conn: sqlite3.Connection, name: str) -> int:
    existing = conn.execute("SELECT id FROM stations WHERE name = ?", (name,)).fetchone()
    if existing is not None:
        return int(existing["id"])
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
        (name, f"https://example.com/{name}"),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_chunk(
    db_path: Path,
    tmp_path: Path,
    *,
    station_name: str = "talk-a",
    start_ts: float = 1000.0,
    end_ts: float = 1090.0,
) -> tuple[int, Path]:
    audio = tmp_path / f"{station_name}-{int(start_ts)}.wav"
    audio.write_bytes(b"fake wav")
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn, station_name)
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, ?, ?, ?, 'processing')
                """,
                (station_id, str(audio), start_ts, end_ts),
            )
            chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    return int(chunk_id), audio


def _loan_extraction(**overrides: object) -> AdExtraction:
    data: dict[str, object] = {
        "is_ad": True,
        "ad_category": "business_funding",
        "company_name": "Rapid Capital Funding",
        "phone_number": "800-555-1212",
        "website": "https://rapid.example",
        "offer_summary": "Working capital up to five hundred thousand dollars",
        "key_claims": ["same-day funding", "bad credit considered"],
        "confidence": 0.93,
    }
    data.update(overrides)
    return AdExtraction.model_validate(data)


def test_estimate_ad_bounds_uses_matching_segments_with_padding() -> None:
    segments = [
        TranscriptSegment(0.0, 10.0, "Traffic and weather together."),
        TranscriptSegment(10.0, 25.0, "Rapid Capital Funding can help your business."),
        TranscriptSegment(25.0, 35.0, "Call now for same-day funding."),
        TranscriptSegment(35.0, 50.0, "Back to the show."),
    ]

    start, end = estimate_ad_bounds(
        segments,
        _loan_extraction(),
        chunk_duration_sec=90.0,
        padding_sec=2.0,
    )

    assert start == 8.0
    assert end == 37.0


def test_record_new_ad_creates_canonical_detection_and_archived_clip(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    chunk_id, audio = _seed_chunk(db_path, tmp_path)
    clipper = FakeClipper()
    persister = DetectionPersister(db_path, settings, archive_dir=tmp_path / "archive", clipper=clipper)

    detection_id = persister.record_extraction(
        chunk_id,
        _loan_extraction(),
        transcript_text="Rapid Capital Funding ad. Call now for same-day funding.",
        segments=[
            TranscriptSegment(0.0, 5.0, "Intro."),
            TranscriptSegment(5.0, 20.0, "Rapid Capital Funding ad."),
            TranscriptSegment(20.0, 30.0, "Call now for same-day funding."),
        ],
    )

    assert detection_id is not None
    conn = get_connection(db_path)
    try:
        canonical = conn.execute("SELECT * FROM canonical_ads").fetchone()
        assert canonical["company_name"] == "Rapid Capital Funding"
        assert canonical["phone_norm"] == "8005551212"
        assert canonical["category"] == "business_funding"
        assert canonical["airing_count"] == 1
        assert canonical["archived_audio_path"].endswith("canonical_ad_1.wav")

        detection = conn.execute("SELECT * FROM detections").fetchone()
        assert detection["canonical_ad_id"] == canonical["id"]
        assert json.loads(detection["key_claims"]) == ["same-day funding", "bad credit considered"]
    finally:
        conn.close()

    assert clipper.calls
    assert clipper.calls[0][0] == audio
    assert clipper.calls[0][2] == 3.0
    assert clipper.calls[0][3] == 32.0


def test_fuzzy_match_reuses_canonical_and_same_station_window_does_not_increment_airings(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    clipper = FakeClipper()
    persister = DetectionPersister(db_path, settings, archive_dir=tmp_path / "archive", clipper=clipper)
    first_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-a", start_ts=1000.0)
    second_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-a", start_ts=1060.0)

    first_id = persister.record_extraction(
        first_chunk_id,
        _loan_extraction(),
        transcript_text="Rapid Capital Funding business funding spot.",
        segments=[TranscriptSegment(0.0, 30.0, "Rapid Capital Funding business funding spot.")],
    )
    second_id = persister.record_extraction(
        second_chunk_id,
        _loan_extraction(
            company_name="Rapid Capital Funding",
            phone_number="800-555-9912",
            offer_summary="Working capital up to $500,000 for your business",
            key_claims=["same day funding", "bad credit is okay"],
        ),
        transcript_text="Rapid Capital Funding offers working capital up to five hundred thousand dollars.",
        segments=[
            TranscriptSegment(
                0.0,
                30.0,
                "Rapid Capital Funding offers working capital up to five hundred thousand dollars.",
            )
        ],
    )

    assert first_id is not None
    assert second_id is not None
    conn = get_connection(db_path)
    try:
        canonical_rows = conn.execute("SELECT * FROM canonical_ads").fetchall()
        assert len(canonical_rows) == 1
        assert canonical_rows[0]["airing_count"] == 1
        detections = conn.execute("SELECT canonical_ad_id FROM detections ORDER BY id").fetchall()
        assert [row["canonical_ad_id"] for row in detections] == [canonical_rows[0]["id"], canonical_rows[0]["id"]]
    finally:
        conn.close()


def test_same_ad_after_window_counts_new_airing(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    persister = DetectionPersister(db_path, settings, archive_dir=tmp_path / "archive", clipper=FakeClipper())
    first_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-a", start_ts=1000.0)
    second_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-a", start_ts=1181.0)

    persister.record_extraction(first_chunk_id, _loan_extraction(), transcript_text="Rapid Capital Funding", segments=[])
    persister.record_extraction(second_chunk_id, _loan_extraction(company_name="Rapid Capital"), transcript_text="Rapid Capital", segments=[])

    conn = get_connection(db_path)
    try:
        airing_count = conn.execute("SELECT airing_count FROM canonical_ads").fetchone()["airing_count"]
        assert airing_count == 2
    finally:
        conn.close()


def test_cross_station_airings_within_window_count_separately(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    persister = DetectionPersister(db_path, settings, archive_dir=tmp_path / "archive", clipper=FakeClipper())
    first_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-a", start_ts=1000.0)
    second_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-b", start_ts=1120.0)

    persister.record_extraction(first_chunk_id, _loan_extraction(), transcript_text="Rapid Capital Funding", segments=[])
    persister.record_extraction(second_chunk_id, _loan_extraction(company_name="Rapid Capital"), transcript_text="Rapid Capital", segments=[])

    conn = get_connection(db_path)
    try:
        airing_count = conn.execute("SELECT airing_count FROM canonical_ads").fetchone()["airing_count"]
        assert airing_count == 2
    finally:
        conn.close()


def test_distinct_ads_do_not_merge_when_category_differs(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    persister = DetectionPersister(db_path, settings, archive_dir=tmp_path / "archive", clipper=FakeClipper())
    first_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-a", start_ts=1000.0)
    second_chunk_id, _ = _seed_chunk(db_path, tmp_path, station_name="talk-b", start_ts=1400.0)

    persister.record_extraction(
        first_chunk_id,
        _loan_extraction(),
        transcript_text="Rapid Capital Funding business funding spot.",
        segments=[],
    )
    persister.record_extraction(
        second_chunk_id,
        _loan_extraction(
            ad_category="debt_relief",
            company_name="Rapid Relief Center",
            phone_number="800-555-1212",
            website="https://relief.example",
            offer_summary="Debt relief help for unsecured balances",
            key_claims=["reduce monthly payments", "free consultation"],
        ),
        transcript_text="Rapid Relief Center debt relief ad.",
        segments=[],
    )

    conn = get_connection(db_path)
    try:
        canonical_rows = conn.execute("SELECT id, category FROM canonical_ads ORDER BY id").fetchall()
        assert [(row["id"], row["category"]) for row in canonical_rows] == [
            (1, "business_funding"),
            (2, "debt_relief"),
        ]
        detections = conn.execute("SELECT canonical_ad_id FROM detections ORDER BY id").fetchall()
        assert [row["canonical_ad_id"] for row in detections] == [1, 2]
    finally:
        conn.close()


def test_non_ads_and_low_confidence_ads_are_not_persisted(
    db_path: Path,
    settings: PipelineSettings,
    tmp_path: Path,
) -> None:
    chunk_id, _ = _seed_chunk(db_path, tmp_path)
    persister = DetectionPersister(db_path, settings, archive_dir=tmp_path / "archive", clipper=FakeClipper())

    assert persister.record_extraction(
        chunk_id,
        _loan_extraction(is_ad=False, confidence=0.2),
        transcript_text="News discussion about lending rates.",
        segments=[],
    ) is None
    assert persister.record_extraction(
        chunk_id,
        _loan_extraction(confidence=0.4),
        transcript_text="Ambiguous mention of funding.",
        segments=[],
    ) is None

    conn = get_connection(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM canonical_ads").fetchone()[0] == 0
    finally:
        conn.close()
