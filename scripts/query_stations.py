"""Query live Docker DB for station-level detection data with full text."""
import sqlite3
import json

DB = "/app/data/pipeline.db"

def q(sql):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(sql)
    rows = c.fetchall()
    conn.close()
    return rows

# Get all detections with station info and transcript text
print("=== DETECTIONS PER STATION ===", flush=True)
rows = q("""
    SELECT st.id, st.name, st.display_name,
           d.id, d.is_ad, d.company_name, d.phone_number, d.website,
           d.offer_summary, d.key_claims,
           c.start_ts, c.end_ts,
           t.text
    FROM detections d
    JOIN chunks c ON c.id = d.chunk_id
    JOIN stations st ON st.id = c.station_id
    LEFT JOIN transcripts t ON t.chunk_id = d.chunk_id
    ORDER BY st.name, c.start_ts DESC
""")

# Group by station
from collections import defaultdict
stations_data = defaultdict(list)
for r in rows:
    sid, sname, sdisplay = r[0], r[1], r[2]
    stations_data[sname].append({
        "detection_id": r[3],
        "is_ad": r[4],
        "company": (r[5] or "").strip(),
        "phone": (r[6] or "").strip(),
        "website": (r[7] or "").strip(),
        "offer": (r[8] or "").strip(),
        "claims": (r[9] or "").strip(),
        "start_ts": r[10],
        "end_ts": r[11],
        "text": (r[12] or "")[:500] if r[12] else ""
    })

# Output as JSON for processing on host
output = {
    "stations": {},
    "station_display": {}
}
for sname, dets in sorted(stations_data.items()):
    # Find display name
    display = ""
    for r in rows:
        if r[1] == sname:
            display = r[2]
            break
    output["stations"][sname] = dets
    output["station_display"][sname] = display

print(f"Stations: {len(stations_data)}", flush=True)
for sname, dets in sorted(stations_data.items()):
    print(f"  {sname}: {len(dets)} detections", flush=True)

# Save for host processing
with open("/tmp/station_detections.json", "w") as f:
    json.dump(output, f, default=str)
print("\n✅ Saved to /tmp/station_detections.json", flush=True)
