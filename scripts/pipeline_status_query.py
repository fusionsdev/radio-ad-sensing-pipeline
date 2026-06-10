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

conn.close()
