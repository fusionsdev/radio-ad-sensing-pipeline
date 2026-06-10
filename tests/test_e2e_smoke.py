"""End-to-end smoke for the in-process worker + alerter slice."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alerter.service import AlerterService
from shared.config import TelegramSettings
from shared.db import get_connection, migrate, transaction
from shared.models import AdExtraction, PipelineSettings
from worker.consumer import ChunkConsumer
from worker.dedup import DetectionPersister
from worker.transcribe import TranscriptSegment, TranscriptionResult


class FakeTranscriber:
    def __init__(self, *, text: str, wall_time_sec: float = 3.0) -> None:
        self.text = text
        self.wall_time_sec = wall_time_sec
        self.calls: list[Path] = []

    def transcribe(
        self,
        audio_path: Path,
        *,
        audio_duration_sec: float | None = None,
    ) -> TranscriptionResult:
        self.calls.append(audio_path)
        duration = audio_duration_sec or 90.0
        return TranscriptionResult(
            text=self.text,
            segments=[
                TranscriptSegment(0.0, 1.0, "Rapid Capital"),
                TranscriptSegment(1.0, 2.5, "same-day business funding"),
            ],
            audio_duration_sec=duration,
            wall_time_sec=self.wall_time_sec,
        )


class FakeExtractor:
    def __init__(self, extraction: AdExtraction) -> None:
        self.extraction = extraction
        self.calls: list[str] = []

    def extract(self, transcript_text: str) -> AdExtraction:
        self.calls.append(transcript_text)
        return self.extraction


def _seed_station(conn, *, name: str = "news-talk") -> int:
    conn.execute(
        "INSERT INTO stations (name, url, enabled) VALUES (?, ?, 1)",
        (name, "https://example.com/live"),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_chunk(
    conn,
    *,
    station_id: int,
    path: str,
    start_ts: float,
    end_ts: float,
) -> int:
    conn.execute(
        """
        INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
        VALUES (?, ?, ?, ?, 'pending')
        """,
        (station_id, path, start_ts, end_ts),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _set_status(conn, key: str, value: str, updated_at: float) -> None:
    conn.execute(
        """
        INSERT INTO status (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, updated_at),
    )


def _today_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()


def _copy_clipper(source: Path, dest: Path, start_sec: float, end_sec: float) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    return dest


def test_smoke_worker_then_alerter_dry_run(tmp_path: Path) -> None:
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)

    now_ts = 1_700_000_000.0
    audio_path = tmp_path / "chunk.wav"
    audio_path.write_bytes(b"fake-audio-bytes")

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(audio_path),
                start_ts=now_ts - 90,
                end_ts=now_ts,
            )
            _set_status(conn, "alerter:digest:date", _today_date(now_ts), now_ts)
    finally:
        conn.close()

    settings = PipelineSettings(queue_max_hours=2, chunk_len=90)
    transcriber = FakeTranscriber(text="Rapid Capital same-day business funding")
    extractor = FakeExtractor(
        AdExtraction(
            is_ad=True,
            ad_category="business_funding",
            company_name="Rapid Capital",
            phone_number="8005551212",
            website="https://rapid.example",
            offer_summary="same-day business funding",
            key_claims=["cash for payroll"],
            confidence=0.94,
        )
    )
    persister = DetectionPersister(
        db_path,
        settings,
        archive_dir=tmp_path / "archive",
        clipper=_copy_clipper,
    )
    consumer = ChunkConsumer(
        db_path,
        settings,
        transcriber,
        extractor=extractor,
        detection_persister=persister,
    )

    assert consumer.run_once() is True
    assert transcriber.calls == [audio_path]
    assert extractor.calls == ["Rapid Capital same-day business funding"]

    conn = get_connection(db_path)
    try:
        chunk = conn.execute("SELECT status, error FROM chunks").fetchone()
        assert chunk["status"] == "done"
        assert chunk["error"] is None

        transcript = conn.execute(
            "SELECT text, segments_json FROM transcripts"
        ).fetchone()
        assert transcript["text"] == "Rapid Capital same-day business funding"
        assert "Rapid Capital" in transcript["segments_json"]

        detection = conn.execute(
            "SELECT alerted, company_name FROM detections"
        ).fetchone()
        assert detection["company_name"] == "Rapid Capital"
        assert detection["alerted"] == 0

        canonical = conn.execute(
            "SELECT company_name, archived_audio_path FROM canonical_ads"
        ).fetchone()
        assert canonical["company_name"] == "Rapid Capital"
        assert Path(canonical["archived_audio_path"]).is_file()
    finally:
        conn.close()

    alerter = AlerterService(
        db_path=db_path,
        settings=settings,
        telegram_settings=TelegramSettings(
            telegram_bot_token=None,
            telegram_chat_id=None,
        ),
        clock=lambda: now_ts,
    )

    summary = alerter.poll_once()

    assert summary == {"first_seen": 1, "ops": 0, "digest": 0}

    conn = get_connection(db_path)
    try:
        alerted = conn.execute("SELECT alerted FROM detections").fetchone()[0]
        assert alerted == 1
    finally:
        conn.close()
