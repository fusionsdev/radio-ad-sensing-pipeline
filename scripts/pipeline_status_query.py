"""Live pipeline DB summary — run inside a worker container via stdin."""
from __future__ import annotations

import sqlite3
import time
import os
from pathlib import Path

db = Path("/app/data/pipeline.db")
if not db.is_file():
    print("ERROR: /app/data/pipeline.db not found in container")
    raise SystemExit(1)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
now = time.time()
window_minutes = 10
window_seconds = window_minutes * 60
processing_stale_after_minutes = int(os.environ.get("PROCESSING_STALE_AFTER_MINUTES", "60"))
stale_cutoff = now - (processing_stale_after_minutes * 60)


def has_column(table: str, column: str) -> bool:
    return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({table})"))


HAS_PROCESSED_AT = has_column("chunks", "processed_at")
HAS_PROCESSING_STARTED_AT = has_column("chunks", "processing_started_at")
HAS_PROCESSING_HEARTBEAT_AT = has_column("chunks", "processing_heartbeat_at")
HAS_WORKER_ID = has_column("chunks", "worker_id")


def time_filter(column: str, seconds: int) -> tuple[str, tuple[float]]:
    return f"{column} >= ?", (now - seconds,)


def one(sql: str, params: tuple = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def scalar_float(sql: str, params: tuple = ()) -> float:
    row = conn.execute(sql, params).fetchone()
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])


def rate_per_minute(sql: str, params: tuple = (), *, minutes: int = window_minutes) -> float:
    return round(one(sql, params) / float(minutes), 2)


print("=== Radio Pipeline Status (live DB) ===")
for row in conn.execute(
    "SELECT status, COUNT(*) AS n FROM chunks GROUP BY status ORDER BY status"
):
    print(f"  chunks.{row['status']}: {row['n']}")

enabled = conn.execute(
    "SELECT name FROM stations WHERE enabled = 1 ORDER BY name"
).fetchall()
names = ", ".join(r["name"] for r in enabled)
print(f"  stations.enabled ({len(enabled)}): {names}")

today = time.time() - (time.time() % 86400)
print(f"  chunks.today: {one('SELECT COUNT(*) FROM chunks WHERE start_ts >= ?', (today,))}")
print(f"  keyword_hits.total: {one('SELECT COUNT(*) FROM keyword_hits')}")
print(f"  canonical_ads: {one('SELECT COUNT(*) FROM canonical_ads')}")
print(f"  detections: {one('SELECT COUNT(*) FROM detections')}")

pending_hours = scalar_float(
    "SELECT COALESCE(SUM(end_ts - start_ts), 0.0) / 3600.0 FROM chunks WHERE status = 'pending'"
)
print(f"  queue.pending_hours: {pending_hours:.2f}")

ingest_where, ingest_params = time_filter("start_ts", window_seconds)
print(
    f"  ingest.rate_{window_minutes}m: "
    f"{rate_per_minute(f'SELECT COUNT(*) FROM chunks WHERE {ingest_where}', ingest_params)} chunks/min"
)

if HAS_PROCESSED_AT:
    done_where, done_params = time_filter("processed_at", window_seconds)
    dropped_where, dropped_params = time_filter("processed_at", 3600)
    done_rate_sql = f"SELECT COUNT(*) FROM chunks WHERE status = 'done' AND {done_where}"
    dropped_backlog_sql = (
        "SELECT COUNT(*) FROM chunks "
        f"WHERE status = 'dropped' AND error = 'dropped_backlog' AND {dropped_where}"
    )
    print(
        f"  worker.done_rate_{window_minutes}m: "
        f"{rate_per_minute(done_rate_sql, done_params)} chunks/min"
    )
    print(
        "  drops.dropped_backlog_1h: "
        f"{one(dropped_backlog_sql, dropped_params)}"
    )
else:
    done_where, done_params = time_filter("start_ts", window_seconds)
    dropped_where, dropped_params = time_filter("start_ts", 3600)
    done_rate_sql = f"SELECT COUNT(*) FROM chunks WHERE status = 'done' AND {done_where}"
    dropped_backlog_sql = (
        "SELECT COUNT(*) FROM chunks "
        f"WHERE status = 'dropped' AND error = 'dropped_backlog' AND {dropped_where}"
    )
    print(
        f"  worker.done_rate_{window_minutes}m: "
        f"{rate_per_minute(done_rate_sql, done_params)} chunks/min (start_ts fallback)"
    )
    print(
        "  drops.dropped_backlog_1h: "
        f"{one(dropped_backlog_sql, dropped_params)} (start_ts fallback)"
    )

if HAS_PROCESSING_HEARTBEAT_AT:
    stale_processing = one(
        """
        SELECT COUNT(*)
        FROM chunks
        WHERE status = 'processing'
          AND (
                (processing_heartbeat_at IS NOT NULL AND processing_heartbeat_at < ?)
             OR (
                    processing_heartbeat_at IS NULL
                AND processing_started_at IS NOT NULL
                AND processing_started_at < ?
                )
             OR (
                    processing_heartbeat_at IS NULL
                AND processing_started_at IS NULL
                AND end_ts < ?
                )
          )
        """,
        (stale_cutoff, stale_cutoff, stale_cutoff),
    )
elif HAS_PROCESSING_STARTED_AT:
    stale_processing = one(
        """
        SELECT COUNT(*)
        FROM chunks
        WHERE status = 'processing'
          AND (
                (processing_started_at IS NOT NULL AND processing_started_at < ?)
             OR (processing_started_at IS NULL AND end_ts < ?)
          )
        """,
        (stale_cutoff, stale_cutoff),
    )
else:
    stale_processing = one(
        "SELECT COUNT(*) FROM chunks WHERE status = 'processing' AND end_ts < ?",
        (stale_cutoff,),
    )
print(f"  worker.stale_processing_rows: {stale_processing}")

duplicate_transcripts = one(
    """
    SELECT COUNT(*)
    FROM (
        SELECT chunk_id
        FROM transcripts
        GROUP BY chunk_id
        HAVING COUNT(*) > 1
    )
    """
)
print(f"  transcripts.duplicate_chunk_ids: {duplicate_transcripts}")

missing_audio_1h = one(
    f"""
    SELECT COUNT(*)
    FROM chunks
    WHERE status = 'dropped'
      AND error LIKE 'missing audio file:%'
      AND {dropped_where}
    """,
    dropped_params,
)
print(f"  drops.missing_audio_file_1h: {missing_audio_1h}")

db_lock_drops_1h = one(
    f"""
    SELECT COUNT(*)
    FROM chunks
    WHERE status = 'dropped'
      AND (LOWER(error) LIKE '%database is locked%' OR LOWER(error) LIKE '%busy%')
      AND {dropped_where}
    """,
    dropped_params,
)
print(f"  drops.db_lock_or_busy_1h: {db_lock_drops_1h}")

if HAS_WORKER_ID and HAS_PROCESSED_AT:
    per_worker = conn.execute(
        """
        SELECT COALESCE(worker_id, '(none)') AS worker_id,
               SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
               SUM(CASE WHEN status = 'dropped' THEN 1 ELSE 0 END) AS dropped
        FROM chunks
        WHERE processed_at >= ?
        GROUP BY COALESCE(worker_id, '(none)')
        ORDER BY done DESC, dropped DESC
        LIMIT 8
        """,
        (now - window_seconds,),
    ).fetchall()
    if per_worker:
        print("  worker.per_worker_10m:")
        for row in per_worker:
            print(f"    {row['worker_id']}: done={row['done']} dropped={row['dropped']}")

top = conn.execute(
    """
    SELECT s.name, COUNT(c.id) AS pending
    FROM stations s
    JOIN chunks c ON c.station_id = s.id AND c.status = 'pending'
    GROUP BY s.id
    ORDER BY pending DESC
    LIMIT 5
    """
).fetchall()
if top:
    print("  top pending by station:")
    for row in top:
        print(f"    {row['name']}: {row['pending']}")

conn.close()
