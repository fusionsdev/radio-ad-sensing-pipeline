"""Live pipeline DB summary — run inside radio-worker container via stdin."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

db = Path("/app/data/pipeline.db")
if not db.is_file():
    print("ERROR: /app/data/pipeline.db not found in container")
    raise SystemExit(1)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row


def one(sql: str, params: tuple = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


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

cfpb = conn.execute(
    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cfpb_complaints_raw'"
).fetchone()
if cfpb:
    print("--- CFPB trademark seeds ---")
    print(f"  cfpb.complaints_raw: {one('SELECT COUNT(*) FROM cfpb_complaints_raw')}")
    print(f"  cfpb.company_entities: {one('SELECT COUNT(*) FROM cfpb_company_entities')}")
    print(f"  cfpb.brand_candidates: {one('SELECT COUNT(*) FROM cfpb_brand_candidates')}")
    last = conn.execute(
        "SELECT status, finished_at FROM cfpb_collection_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if last:
        print(f"  cfpb.last_run: {last['status']} @ {last['finished_at'] or 'in progress'}")
    top_co = conn.execute(
        """
        SELECT company_normalized, complaint_count, trademark_candidate_score
        FROM cfpb_company_entities
        ORDER BY complaint_count DESC LIMIT 5
        """
    ).fetchall()
    if top_co:
        print("  cfpb.top companies:")
        for row in top_co:
            print(
                f"    {row['company_normalized']}: "
                f"{row['complaint_count']} complaints, score {row['trademark_candidate_score']:.0f}"
            )

conn.close()
