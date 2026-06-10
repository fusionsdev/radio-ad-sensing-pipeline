"""Drain pending chunks once — operator smoke helper."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from shared.config import load_settings
from shared.db import get_connection, migrate
from shared.logging import setup_logging
from worker.consumer import create_consumer


def main() -> int:
    setup_logging("worker-smoke")
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/pipeline.db")
    migrate(db_path)
    settings = load_settings()
    use_cpu = os.environ.get("ASR_DEVICE", "").lower() == "cpu"

    def model_factory(model_name: str, compute_type: str):
        from faster_whisper import WhisperModel

        if use_cpu:
            return WhisperModel(model_name, device="cpu", compute_type="int8")
        return WhisperModel(model_name, compute_type=compute_type)

    transcriber = None
    if use_cpu:
        transcriber = __import__("worker.transcribe", fromlist=["Transcriber"]).Transcriber(
            settings,
            model_factory=model_factory,
        )

    consumer = create_consumer(db_path, settings, transcriber=transcriber)

    max_chunks = int(os.environ.get("SMOKE_MAX_CHUNKS", "0"))

    processed = 0
    start = time.time()
    while True:
        if consumer.run_once():
            processed += 1
            print(f"processed_chunk total={processed}", flush=True)
            if max_chunks and processed >= max_chunks:
                break
            continue

        conn = get_connection(db_path)
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE status = 'pending'"
            ).fetchone()[0]
        finally:
            conn.close()

        if pending == 0:
            break
        time.sleep(1.0)

    elapsed = time.time() - start
    conn = get_connection(db_path)
    try:
        chunk_counts = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT status, COUNT(*) FROM chunks GROUP BY status"
            )
        }
        transcripts = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        detections = conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
        ads = conn.execute("SELECT COUNT(*) FROM canonical_ads").fetchone()[0]
        dropped_errors = conn.execute(
            "SELECT error, COUNT(*) FROM chunks WHERE status = 'dropped' GROUP BY error"
        ).fetchall()
    finally:
        conn.close()

    print(
        "SUMMARY",
        {
            "elapsed_sec": round(elapsed, 1),
            "processed": processed,
            "chunks": chunk_counts,
            "transcripts": transcripts,
            "detections": detections,
            "canonical_ads": ads,
            "dropped_errors": dropped_errors,
        },
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
