"""Seed a database with sample dashboard data for dev and tests."""

from __future__ import annotations

import json
import time
import wave
from pathlib import Path

from shared.db import get_connection, migrate, transaction

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = PROJECT_ROOT / "data" / "ad_archive"


def _write_silent_wav(path: Path, *, duration_s: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * n_frames)


def seed_dashboard_db(db_path: Path, *, archive_dir: Path | None = None) -> dict[str, int]:
    """Migrate and insert fake stations, chunks, ads, detections, gaps."""
    archive = archive_dir or ARCHIVE_DIR
    migrate(db_path)
    now = time.time()
    audio_abs = archive / "seed-ad-1.wav"
    _write_silent_wav(audio_abs)
    stored_audio_path = str(audio_abs.resolve())

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                "INSERT INTO stations (name, url, format, enabled) VALUES (?, ?, ?, 1)",
                ("news-talk", "https://example.com/news.mp3", "mp3"),
            )
            conn.execute(
                "INSERT INTO stations (name, url, format, enabled) VALUES (?, ?, ?, 0)",
                ("sports-fm", "https://example.com/sports.mp3", "mp3"),
            )
            station_id = conn.execute(
                "SELECT id FROM stations WHERE name = 'news-talk'"
            ).fetchone()[0]

            conn.execute(
                """
                INSERT INTO canonical_ads (
                    company_name, phone_norm, category,
                    first_seen, last_seen, airing_count, archived_audio_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Acme Funding",
                    "8005551234",
                    "business_loan",
                    now - 86400,
                    now - 3600,
                    2,
                    stored_audio_path,
                ),
            )
            ad_id = conn.execute("SELECT id FROM canonical_ads").fetchone()[0]

            for i, status in enumerate(["done", "pending", "done"]):
                start = now - 7200 + i * 90
                end = start + 90
                conn.execute(
                    """
                    INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        station_id,
                        f"data/chunks/chunk-{i}.wav",
                        start,
                        end,
                        status,
                    ),
                )
            chunk_ids = [
                row[0]
                for row in conn.execute("SELECT id FROM chunks ORDER BY id").fetchall()
            ]

            for chunk_id in chunk_ids[:2]:
                conn.execute(
                    "INSERT INTO transcripts (chunk_id, text, asr_duration_ms) VALUES (?, ?, ?)",
                    (
                        chunk_id,
                        "Call Acme Funding at 800-555-1234 for fast business loans today.",
                        1200,
                    ),
                )

            conn.execute(
                """
                INSERT INTO detections (
                    chunk_id, canonical_ad_id, is_ad, ad_category, company_name,
                    phone_number, offer_summary, key_claims, confidence, alerted
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    chunk_ids[0],
                    ad_id,
                    "business_loan",
                    "Acme Funding",
                    "8005551234",
                    "Fast funding up to $500k",
                    json.dumps(["same-day approval"]),
                    0.92,
                ),
            )
            detection_id = conn.execute("SELECT id FROM detections").fetchone()[0]

            conn.execute(
                """
                INSERT INTO gaps (station_id, start_ts, end_ts, reason)
                VALUES (?, ?, ?, ?)
                """,
                (station_id, now - 4000, now - 3900, "stream down"),
            )

        return {
            "station_id": station_id,
            "ad_id": ad_id,
            "detection_id": detection_id,
            "chunk_ids": chunk_ids,
        }
    finally:
        conn.close()
