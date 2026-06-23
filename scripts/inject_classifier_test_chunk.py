"""Enqueue a pending chunk for live worker classifier smoke tests.

Usage (inside worker container or host venv with shared DB path):

    python scripts/inject_classifier_test_chunk.py \\
        --wav /path/to/test.wav \\
        --station klif-am-570 \\
        --db /app/data/pipeline.db \\
        --jump-queue

Generate speech on Windows host first (PowerShell):

    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $s.SetOutputToWaveFile('data/classifier-test-accept.wav')
    $s.Speak('Need a personal loan today? Call now for fast cash with low monthly payments. Apply online. Fast approval from trusted lenders.')
    $s.Dispose()

Then copy WAV into the shared chunk tmpfs and enqueue:

    docker cp data/classifier-test-accept.wav radio-worker:/app/chunks/klif-am-570/<ts>.wav
    docker exec radio-worker python /tmp/inject_classifier_test_chunk.py ...
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from shared.config import load_stations
from shared.db import get_connection, retry_on_busy, transaction
from shared.models import ChunkStatus


@retry_on_busy()
def _upsert_station_id(db_path: Path, station_name: str) -> int:
    stations = {s.name: s for s in load_stations()}
    if station_name not in stations:
        raise SystemExit(f"unknown station: {station_name}")
    station = stations[station_name]
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO stations (name, url, format, enabled, display_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    url = excluded.url,
                    format = excluded.format,
                    enabled = excluded.enabled,
                    display_name = excluded.display_name
                """,
                (
                    station.name,
                    station.url,
                    station.format,
                    1 if station.enabled else 0,
                    station.display_name,
                ),
            )
            row = conn.execute(
                "SELECT id FROM stations WHERE name = ?",
                (station.name,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"station upsert failed: {station.name}")
            return int(row["id"])
    finally:
        conn.close()


@retry_on_busy()
def _enqueue_chunk(
    db_path: Path,
    *,
    station_id: int,
    path: str,
    start_ts: float,
    end_ts: float,
) -> int:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (station_id, path, start_ts, end_ts, ChunkStatus.PENDING.value),
            )
            return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        conn.close()


def _pending_backlog_seconds(db_path: Path) -> float:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT start_ts, end_ts FROM chunks WHERE status = 'pending'"
        ).fetchall()
        return sum(float(row["end_ts"]) - float(row["start_ts"]) for row in rows)
    finally:
        conn.close()


def _queue_max_seconds(db_path: Path) -> float:
    from shared.config import load_settings

    settings = load_settings()
    if settings.db_path and Path(settings.db_path) != db_path:
        # Container path override — queue cap is global config, not DB-specific.
        pass
    return float(settings.queue_max_hours * 3600)


def _choose_start_ts(db_path: Path, *, jump_queue: bool, duration_sec: float) -> float:
    now = time.time()
    if not jump_queue:
        return now

    backlog = _pending_backlog_seconds(db_path)
    max_seconds = _queue_max_seconds(db_path)
    if backlog + duration_sec > max_seconds:
        raise SystemExit(
            "pending backlog too close to queue_max_hours — "
            f"{backlog:.0f}s + {duration_sec:.0f}s > {max_seconds:.0f}s. "
            "Retry without --jump-queue or wait for worker to drain."
        )

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT MIN(start_ts) AS min_ts FROM chunks WHERE status = 'pending'"
        ).fetchone()
        min_ts = row["min_ts"] if row is not None else None
    finally:
        conn.close()
    if min_ts is None:
        return now
    return float(min_ts) - 1.0


def _drop_oldest_pending(db_path: Path, *, need_seconds: float) -> int:
    """Drop oldest pending chunks until backlog + need_seconds fits queue_max_hours."""
    dropped = 0
    while True:
        backlog = _pending_backlog_seconds(db_path)
        max_seconds = _queue_max_seconds(db_path)
        if backlog + need_seconds <= max_seconds:
            break
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                """
                SELECT id FROM chunks
                WHERE status = 'pending'
                ORDER BY start_ts ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                break
            with transaction(conn):
                conn.execute(
                    """
                    UPDATE chunks
                    SET status = 'dropped', error = 'classifier_test_make_room'
                    WHERE id = ?
                    """,
                    (row["id"],),
                )
            dropped += 1
        finally:
            conn.close()
    return dropped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", type=Path, required=True, help="Source WAV file")
    parser.add_argument("--station", default="klif-am-570")
    parser.add_argument("--db", type=Path, default=Path("data/pipeline.db"))
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("/app/chunks"),
        help="Chunk tmpfs root (ingestor+worker shared)",
    )
    parser.add_argument(
        "--duration-sec",
        type=float,
        default=15.0,
        help="start_ts/end_ts span stored on the chunk row",
    )
    parser.add_argument(
        "--jump-queue",
        action="store_true",
        help="Use start_ts just before oldest pending chunk",
    )
    parser.add_argument(
        "--make-room",
        action="store_true",
        help="Drop oldest pending chunks until jump-queue inject fits queue_max_hours",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print paths only; do not copy or enqueue",
    )
    parser.add_argument(
        "--process-now",
        action="store_true",
        help="Run worker consumer once after enqueue (stop radio-worker first to avoid races)",
    )
    args = parser.parse_args()

    if not args.wav.is_file():
        raise SystemExit(f"WAV not found: {args.wav}")

    if args.make_room and args.jump_queue and not args.dry_run:
        dropped = _drop_oldest_pending(
            args.db,
            need_seconds=args.duration_sec + 60.0,
        )
        if dropped:
            print(f"dropped_oldest_pending={dropped}")

    ts_ms = int(time.time() * 1000)
    dest_dir = args.chunks_dir / args.station
    dest_path = dest_dir / f"{ts_ms}.wav"

    start_ts = _choose_start_ts(
        args.db,
        jump_queue=args.jump_queue,
        duration_sec=args.duration_sec,
    )
    end_ts = start_ts + args.duration_sec

    print(f"station={args.station}")
    print(f"dest_path={dest_path}")
    print(f"start_ts={start_ts} end_ts={end_ts} jump_queue={args.jump_queue}")

    if args.dry_run:
        return

    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.wav, dest_path)

    station_id = _upsert_station_id(args.db, args.station)
    chunk_id = _enqueue_chunk(
        args.db,
        station_id=station_id,
        path=str(dest_path),
        start_ts=start_ts,
        end_ts=end_ts,
    )
    print(f"chunk_id={chunk_id} status=pending")
    print("Watch: docker logs radio-worker -f 2>&1 | findstr /i \"keyword classifier chunk transcribed\"")

    if args.process_now:
        from shared.config import load_settings
        from worker.consumer import create_consumer

        settings = load_settings()
        consumer = create_consumer(args.db, settings)
        for attempt in range(1, 121):
            conn = get_connection(args.db)
            try:
                row = conn.execute(
                    "SELECT status FROM chunks WHERE id = ?",
                    (chunk_id,),
                ).fetchone()
            finally:
                conn.close()
            if row is None:
                raise SystemExit(f"chunk {chunk_id} missing")
            if row["status"] in {"done", "dropped"}:
                print(f"chunk_id={chunk_id} final_status={row['status']} attempts={attempt - 1}")
                break
            consumer.run_once()
        else:
            raise SystemExit(f"chunk {chunk_id} not finished after 120 run_once attempts")


if __name__ == "__main__":
    main()
