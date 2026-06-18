"""Tests for the Telegram outbound alerter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from alerter.service import AlerterService
from shared.config import TelegramSettings
from shared.db import get_connection, migrate, transaction


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
    status: str = "pending",
) -> int:
    conn.execute(
        """
        INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (station_id, path, start_ts, end_ts, status),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_detection(
    conn,
    *,
    chunk_id: int,
    canonical_ad_id: int,
    company_name: str = "Acme Funding",
    alerted: int = 0,
) -> int:
    conn.execute(
        """
        INSERT INTO detections (
            chunk_id, canonical_ad_id, is_ad, ad_category, company_name,
            phone_number, website, offer_summary, key_claims, confidence, alerted
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            canonical_ad_id,
            "business_loan",
            company_name,
            "8005551234",
            "https://acme.example",
            "Fast funding",
            json.dumps(["same-day approval"]),
            0.95,
            alerted,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_canonical_ad(
    conn,
    *,
    company_name: str,
    archived_audio_path: str | None = None,
) -> int:
    conn.execute(
        """
        INSERT INTO canonical_ads (
            company_name, phone_norm, category, first_seen, last_seen, airing_count, archived_audio_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_name,
            "8005551234",
            "business_loan",
            1_700_000_000.0,
            1_700_000_000.0,
            1,
            archived_audio_path,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _seed_transcript(conn, *, chunk_id: int, text: str) -> None:
    conn.execute(
        """
        INSERT INTO transcripts (chunk_id, text, asr_duration_ms)
        VALUES (?, ?, ?)
        """,
        (chunk_id, text, 9000),
    )


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


class TelegramRecorder:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            body = request.read()
            self.requests.append(
                (
                    request.method,
                    request.url.path,
                    dict(request.headers),
                    body,
                )
            )
            return httpx.Response(200, json={"ok": True, "result": {}})

        return httpx.MockTransport(handler)


def _today_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()


def test_first_seen_alert_sends_message_and_audio_and_marks_alerted(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "alerter.db"
    migrate(db_path)
    archive_dir = tmp_path / "ad_archive"
    archive_dir.mkdir()
    archive = archive_dir / "archive.wav"
    archive.write_bytes(b"fake-audio")
    now_ts = 1_700_000_000.0

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk.wav"),
                start_ts=now_ts - 60,
                end_ts=now_ts,
            )
            canonical_id = _seed_canonical_ad(conn, company_name="Acme Funding", archived_audio_path=str(archive))
            _seed_detection(conn, chunk_id=chunk_id, canonical_ad_id=canonical_id)
            _set_status(conn, "alerter:digest:date", _today_date(now_ts), now_ts)
    finally:
        conn.close()

    recorder = TelegramRecorder()
    service = AlerterService(
        db_path=db_path,
        telegram_settings=TelegramSettings(
            telegram_bot_token="token",
            telegram_chat_id="chat",
        ),
        transport=recorder.transport(),
        clock=lambda: now_ts,
        archive_dir=archive_dir,
    )

    summary = service.poll_once()

    assert summary["first_seen"] == 1
    assert summary["ops"] == 0
    assert summary["digest"] == 0
    assert len(recorder.requests) == 2
    assert recorder.requests[0][1].endswith("/sendMessage")
    assert b"First-seen ad alert" in recorder.requests[0][3]
    assert b"Acme Funding" in recorder.requests[0][3]
    assert recorder.requests[1][1].endswith("/sendAudio")
    assert b"archive.wav" in recorder.requests[1][3]

    conn = get_connection(db_path)
    try:
        alerted = conn.execute("SELECT alerted FROM detections").fetchone()[0]
        assert alerted == 1
    finally:
        conn.close()


def test_first_seen_alert_includes_transcript_excerpt(tmp_path: Path) -> None:
    db_path = tmp_path / "alerter.db"
    migrate(db_path)
    now_ts = 1_700_000_000.0
    transcript = "Call Rapid Capital now for same-day business funding up to five hundred thousand dollars."

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk.wav"),
                start_ts=now_ts - 60,
                end_ts=now_ts,
            )
            _seed_transcript(conn, chunk_id=chunk_id, text=transcript)
            canonical_id = _seed_canonical_ad(conn, company_name="Rapid Capital")
            _seed_detection(conn, chunk_id=chunk_id, canonical_ad_id=canonical_id)
            _set_status(conn, "alerter:digest:date", _today_date(now_ts), now_ts)
    finally:
        conn.close()

    recorder = TelegramRecorder()
    service = AlerterService(
        db_path=db_path,
        telegram_settings=TelegramSettings(
            telegram_bot_token="token",
            telegram_chat_id="chat",
        ),
        transport=recorder.transport(),
        clock=lambda: now_ts,
    )

    service.poll_once()

    assert b"Transcript:" in recorder.requests[0][3]
    assert b"Rapid Capital now for same-day" in recorder.requests[0][3]


def test_dry_run_without_token_marks_alerted_and_does_not_crash(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "alerter.db"
    migrate(db_path)
    now_ts = 1_700_000_000.0

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn)
            chunk_id = _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk.wav"),
                start_ts=now_ts - 60,
                end_ts=now_ts,
            )
            canonical_id = _seed_canonical_ad(conn, company_name="Dry Run Funding")
            _seed_detection(conn, chunk_id=chunk_id, canonical_ad_id=canonical_id)
            _set_status(conn, "alerter:digest:date", _today_date(now_ts), now_ts)
    finally:
        conn.close()

    service = AlerterService(
        db_path=db_path,
        telegram_settings=TelegramSettings(
            telegram_bot_token=None,
            telegram_chat_id=None,
        ),
        clock=lambda: now_ts,
    )

    summary = service.poll_once()

    assert summary["first_seen"] == 1
    conn = get_connection(db_path)
    try:
        alerted = conn.execute("SELECT alerted FROM detections").fetchone()[0]
        assert alerted == 1
    finally:
        conn.close()


def test_station_down_alert_sends_once_per_outage(tmp_path: Path) -> None:
    db_path = tmp_path / "alerter.db"
    migrate(db_path)
    now_ts = 1_700_000_000.0
    first_chunk_ts = now_ts - 2 * 3600
    outage_start = first_chunk_ts

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn, name="news-talk")
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk.wav"),
                start_ts=first_chunk_ts - 90,
                end_ts=first_chunk_ts,
            )
            conn.execute(
                "INSERT INTO gaps (station_id, start_ts, end_ts, reason) VALUES (?, ?, ?, ?)",
                (station_id, outage_start, outage_start + 90.0, "stream_down"),
            )
            _set_status(conn, "alerter:digest:date", _today_date(now_ts), now_ts)
    finally:
        conn.close()

    recorder = TelegramRecorder()
    service = AlerterService(
        db_path=db_path,
        telegram_settings=TelegramSettings(
            telegram_bot_token="token",
            telegram_chat_id="chat",
        ),
        transport=recorder.transport(),
        clock=lambda: now_ts,
    )

    summary = service.poll_once()
    assert summary["ops"] == 1
    assert len(recorder.requests) == 1
    assert b"station down" in recorder.requests[0][3].lower()
    assert b"news-talk" in recorder.requests[0][3]

    summary = service.poll_once()
    assert summary["ops"] == 0
    assert len(recorder.requests) == 1


def test_queue_drop_alert_reports_new_drops_once(tmp_path: Path) -> None:
    db_path = tmp_path / "alerter.db"
    migrate(db_path)
    now_ts = 1_700_000_000.0
    station_id = 0

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn, name="news-talk")
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk-1.wav"),
                start_ts=now_ts - 180,
                end_ts=now_ts - 90,
                status="dropped",
            )
            _set_status(conn, "alerter:digest:date", _today_date(now_ts), now_ts)
    finally:
        conn.close()

    recorder = TelegramRecorder()
    service = AlerterService(
        db_path=db_path,
        telegram_settings=TelegramSettings(
            telegram_bot_token="token",
            telegram_chat_id="chat",
        ),
        transport=recorder.transport(),
        clock=lambda: now_ts,
    )

    summary = service.poll_once()
    assert summary["ops"] == 1
    assert len(recorder.requests) == 1
    assert b"queue drops" in recorder.requests[0][3].lower()
    assert b"New dropped chunks: 1" in recorder.requests[0][3]

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk-2.wav"),
                start_ts=now_ts - 60,
                end_ts=now_ts,
                status="dropped",
            )
    finally:
        conn.close()

    summary = service.poll_once()
    assert summary["ops"] == 1
    assert len(recorder.requests) == 2
    assert b"New dropped chunks: 1" in recorder.requests[1][3]


def test_daily_digest_only_sends_once_per_day(tmp_path: Path) -> None:
    db_path = tmp_path / "alerter.db"
    migrate(db_path)
    now_ts = 1_700_000_000.0

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            station_id = _seed_station(conn, name="news-talk")
            _seed_chunk(
                conn,
                station_id=station_id,
                path=str(tmp_path / "chunk.wav"),
                start_ts=now_ts - 60,
                end_ts=now_ts,
            )
    finally:
        conn.close()

    recorder = TelegramRecorder()
    service = AlerterService(
        db_path=db_path,
        telegram_settings=TelegramSettings(
            telegram_bot_token="token",
            telegram_chat_id="chat",
        ),
        transport=recorder.transport(),
        clock=lambda: now_ts,
    )

    summary = service.poll_once()
    assert summary["digest"] == 1
    assert len(recorder.requests) == 1
    assert b"Daily digest" in recorder.requests[0][3]
    assert b"Pending queue: 1" in recorder.requests[0][3]

    summary = service.poll_once()
    assert summary["digest"] == 0
    assert len(recorder.requests) == 1


def test_resolve_audio_path_rejects_paths_outside_archive(tmp_path: Path) -> None:
    # A traversal value in the stored path must not be uploaded to Telegram.
    archive_dir = tmp_path / "ad_archive"
    archive_dir.mkdir()
    inside = archive_dir / "ok.wav"
    inside.write_bytes(b"x")
    outside = tmp_path / "secret.wav"
    outside.write_bytes(b"secret")

    service = AlerterService(
        db_path=tmp_path / "alerter.db",
        telegram_settings=TelegramSettings(),
        archive_dir=archive_dir,
    )

    assert service._resolve_audio_path(str(inside)) == inside.resolve()
    assert service._resolve_audio_path(str(outside)) is None
    assert service._resolve_audio_path("../../secret.wav") is None
    assert service._resolve_audio_path(None) is None
