"""
Generate 48h loan station batch plan after stream verification + strict classifier results.
"""
import csv
import json
from datetime import datetime

# ── Load current station performance ──────────────────────────────
with open("exports/loan_only_station_rotation_plan.csv") as f:
    current = list(csv.DictReader(f))
scores = {r["station"]: r for r in current}

# ── Load stream validation data ───────────────────────────────────
with open("data/stream_validation_results.json") as f:
    validated = json.load(f)
validated_stations = {v["call_sign"].lower().replace(" ", ""): v for v in validated}

# ── Station config (from stations.yaml) ───────────────────────────
# Key: station call_sign (lower)
station_config = {
    "klif-am-570": {"market": "Dallas, TX", "url": "http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3", "state": "TX", "format": "Talk"},
    "wbap-am-820": {"market": "Dallas–Fort Worth, TX", "url": "http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3", "state": "TX", "format": "News/Talk"},
    "ktrh-am-740": {"market": "Houston, TX", "url": "http://stream.revma.ihrhls.com/zc2285", "state": "TX", "format": "Talk"},
    "wsb-am-750": {"market": "Atlanta, GA", "url": "http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3", "state": "GA", "format": "News/Talk"},
    "woai-am-1200": {"market": "San Antonio, TX", "url": "http://stream.revma.ihrhls.com/zc2361", "state": "TX", "format": "Talk"},
    "klbj-am-590": {"market": "Austin, TX", "url": "http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls", "state": "TX", "format": "News/Talk"},
    "wgul-860": {"market": "Tampa, FL", "url": "http://208.80.52.107/WGULAM_SC", "state": "FL", "format": "News/Talk"},
    "kabc-am-790": {"market": "Los Angeles, CA", "url": "http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3", "state": "CA", "format": "Talk"},
    "whbo-1040": {"market": "Tampa, FL", "url": "https://ice41.securenetsystems.net/WHBO", "state": "FL", "format": "Talk"},
    "wibc-fm-931": {"market": "Indianapolis, IN", "url": "http://playerservices.streamtheworld.com/api/livestream-redirect/WIBCFM.mp3", "state": "IN", "format": "News/Talk"},
    "wwtn-fm-997": {"market": "Nashville, TN", "url": "http://playerservices.streamtheworld.com/api/livestream-redirect/WWTNFM.mp3", "state": "TN", "format": "News/Talk"},
    "wtam-am-1100": {"market": "Cleveland, OH", "url": "http://stream.revma.ihrhls.com/zc1757", "state": "OH", "format": "Talk"},
}

# ── Proposed batch ────────────────────────────────────────────────
batch = [
    # Keep — proven loan stations
    ("keep", "ktrh-am-740", "TX", "Houston", "Talk",
     "http://stream.revma.ihrhls.com/zc2285",
     "10 loan ads, 6 unique advertisers. Stream verified (iHeart)."),
    
    ("keep", "klif-am-570", "TX", "Dallas", "Talk",
     "http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3",
     "12 loan ads, 9 unique advertisers. Stream verified (StreamTheWorld)."),
    
    ("keep", "wsb-am-750", "GA", "Atlanta", "News/Talk",
     "http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3",
     "15 loan ads, 6 unique advertisers. Stream verified (StreamGuys)."),
    
    ("keep", "wbap-am-820", "TX", "Dallas–Fort Worth", "News/Talk",
     "http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3",
     "13 loan ads, 8 unique advertisers. Stream verified (StreamTheWorld)."),
    
    # Add — new stations to test
    ("add", "klbj-am-590", "TX", "Austin", "News/Talk",
     "http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls",
     "Austin market gap. Stream had 403 on 2026-06-10. Needs re-test. Enabled=false."),
    
    ("add", "wgul-860", "FL", "Tampa", "News/Talk",
     "http://208.80.52.107/WGULAM_SC",
     "Tampa has WHBO only. Stream had 403 on 2026-06-10. Needs re-test. Enabled=false."),
    
    ("add", "kabc-am-790", "CA", "Los Angeles", "Talk",
     "http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3",
     "2 loan ads, 2 unique. Weak signal but LA is major market. Enable and re-test."),
    
    # Rotate out — pause these from loan batch (may be re-enabled later)
    ("pause", "woai-am-1200", "TX", "San Antonio", "Talk",
     "http://stream.revma.ihrhls.com/zc2361",
     "Rotated out. Only 3 loan ads — too weak for batch slot. Replace with KLBJ (Austin)."),
    
    ("pause", "wwtn-fm-997", "TN", "Nashville", "News/Talk",
     "http://playerservices.streamtheworld.com/api/livestream-redirect/WWTNFM.mp3",
     "Rotated out. Only 1 unique loan advertiser. Replace with WGUL (Tampa)."),
    
    ("pause", "whbo-1040", "FL", "Tampa", "Talk",
     "https://ice41.securenetsystems.net/WHBO",
     "Rotated out. Only 2 loan ads across 485 detections. Replace with KABC (LA)."),
    
    # Already rotated out — confirm
    ("pause", "wtam-am-1100", "OH", "Cleveland", "Talk",
     "http://stream.revma.ihrhls.com/zc1757",
     "Confirmed rotate out. 0 loan ads in 50 detections."),
    
    ("pause", "wibc-fm-931", "IN", "Indianapolis", "News/Talk",
     "http://playerservices.streamtheworld.com/api/livestream-redirect/WIBCFM.mp3",
     "Rotated out. 5 loan ads is borderline, freeing slot for new market test."),
]

# ═══════════════════════════════════════════════════════════════════
# FILE 1: Batch Plan (MD)
# ═══════════════════════════════════════════════════════════════════

with open("exports/next_48h_loan_station_batch.md", "w") as f:
    f.write("# Next 48h Loan Station Batch\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"**Tool**: Strict loan classifier (v2, phrase-level, exclusion-aware)\n\n")
    
    f.write("## Batch Summary\n\n")
    keep_count = sum(1 for b in batch if b[0] == "keep")
    add_count = sum(1 for b in batch if b[0] == "add")
    pause_count = sum(1 for b in batch if b[0] == "pause")
    
    f.write(f"| Action | Count | Stations |\n")
    f.write(f"|---|---:|---|\n")
    f.write(f"| ✅ Keep | {keep_count} | {', '.join(b[1] for b in batch if b[0]=='keep')} |\n")
    f.write(f"| 🆕 Add | {add_count} | {', '.join(b[1] for b in batch if b[0]=='add')} |\n")
    f.write(f"| ⏸️ Pause | {pause_count} | {', '.join(b[1] for b in batch if b[0]=='pause')} |\n")
    
    f.write(f"\n**Total active**: {keep_count + add_count} stations for 48h\n\n")
    
    f.write("## Station Batch\n\n")
    f.write("| Action | Callsign | State | Market | Format | Stream URL | Reason |\n")
    f.write("|:---|:---|:---|:---|---:|:---|:---|\n")
    
    for action, callsign, state, market, fmt, url, reason in batch:
        icon = {"keep": "✅", "add": "🆕", "pause": "⏸️"}[action]
        f.write(f"| {icon} {action} | {callsign} | {state} | {market} | {fmt} | `{url}` | {reason} |\n")
    
    f.write("\n## Coverage Map\n\n")
    f.write("| Region | Stations | Markets Covered |\n")
    f.write("|---|---:|---|\n")
    f.write("| **Texas** | KTRH, KLIF, WBAP, KLBJ | Houston, Dallas, Austin |\n")
    f.write("| **Southeast** | WSB, WGUL | Atlanta, Tampa |\n")
    f.write("| **West Coast** | KABC | Los Angeles |\n\n")
    
    f.write("## Risks\n\n")
    f.write("1. **KLBJ (Austin)**: Stream had 403 error on 2026-06-10. `Enabled=false`. Must re-test before batch starts.\n")
    f.write("2. **WGUL (Tampa)**: Stream had 403 error on 2026-06-10. `Enabled=false`. Must re-test before batch starts.\n")
    f.write("3. **KABC (Los Angeles)**: Stream had `empty_chunk` loop on 2026-06-10. `Enabled=false`. Must re-test.\n")
    f.write("4. **WLW, KNTH, KTSA, WFLA**: Not in station config. Cannot add without stream discovery first.\n\n")
    
    f.write("## Success Criteria (after 48h)\n\n")
    f.write("| Criteria | Threshold | Action |\n")
    f.write("|---|---|---|\n")
    f.write("| 2+ unique loan advertisers | Pass | Keep in batch |\n")
    f.write("| 1 named loan advertiser | Marginal | Watch — 48h more |\n")
    f.write("| 0 loan advertisers | Fail | Rotate out |\n")
    f.write("| Mostly debt/tax/insurance | Fail | Rotate out |\n")
    f.write("| Classifier precision < 70% | Audit | Fix classifier before keeping |\n")

print("✅ exports/next_48h_loan_station_batch.md", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 2: Batch Plan (CSV)
# ═══════════════════════════════════════════════════════════════════

with open("exports/next_48h_loan_station_batch.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["action", "callsign", "state", "market", "format", "stream_url", "reason", "loan_ads", "unique_loan"])
    for action, callsign, state, market, fmt, url, reason in batch:
        loan = scores[callsign]["loan_ads"] if callsign in scores else "new"
        unique = scores[callsign]["unique_loan_advertisers"] if callsign in scores else "new"
        w.writerow([action, callsign, state, market, fmt, url, reason, loan, unique])

print("✅ exports/next_48h_loan_station_batch.csv", flush=True)

# ═══════════════════════════════════════════════════════════════════
# FILE 3: Rotation Commands
# ═══════════════════════════════════════════════════════════════════

with open("exports/station_rotation_commands.md", "w") as f:
    f.write("# Station Rotation Commands\n\n")
    f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    
    f.write("## Config Changes Required\n\n")
    f.write("Edit `config/stations.yaml`:\n\n")
    
    f.write("### Enable (set to `enabled: true`)\n\n")
    f.write("```yaml\n")
    for action, callsign, state, market, fmt, url, reason in batch:
        if action == "add":
            f.write(f"  - name: {callsign}\n")
            f.write(f"    enabled: true  # ADDED for 48h loan batch\n")
    f.write("```\n\n")
    
    f.write("### Keep Enabled (already `enabled: true`)\n\n")
    f.write("```yaml\n")
    for action, callsign, state, market, fmt, url, reason in batch:
        if action == "keep":
            f.write(f"  - name: {callsign}  # KEEP — {scores[callsign]['loan_ads']} loan ads\n")
    f.write("```\n\n")
    
    f.write("### Disable (set to `enabled: false`)\n\n")
    f.write("```yaml\n")
    for action, callsign, state, market, fmt, url, reason in batch:
        if action == "pause":
            note = scores[callsign]['loan_ads'] if callsign in scores else "N/A"
            f.write(f"  - name: {callsign}  # PAUSE — {note} loan ads (loan batch rotation)\n")
    f.write("```\n\n")
    
    f.write("## Rebuild and Restart\n\n")
    f.write("After editing `config/stations.yaml`:\n\n")
    f.write("```bash\n")
    f.write("docker compose up -d --force-recreate ingestor\n")
    f.write("```\n\n")
    
    f.write("## Verification Commands\n\n")
    f.write("```bash\n")
    f.write("# Check ingestor is running all 10 stations\n")
    f.write("docker compose logs ingestor --tail 50\n\n")
    f.write("# Check chunk production (after 15min)\n")
    f.write("docker compose exec worker sqlite3 /app/data/pipeline.db \"\n")
    f.write("  SELECT s.name, COUNT(c.id) as chunks\n")
    f.write("  FROM chunks c JOIN stations s ON s.id = c.station_id\n")
    f.write("  WHERE c.created_at > datetime('now', '-1 hour')\n")
    f.write("  GROUP BY s.name ORDER BY chunks DESC;")
    f.write("\n")
    f.write("# Check loan detections after 48h\n")
    f.write("docker compose exec worker python /tmp/loan_audit.py\n")
    f.write("```\n\n")
    
    f.write("## 48h Evaluation Timeline\n\n")
    f.write("| Time | Action |\n")
    f.write("|---|---|\n")
    f.write("| T+0h | Apply config changes, restart ingestor |\n")
    f.write("| T+1h | Verify all 10 streams producing chunks |\n")
    f.write("| T+24h | Quick check — any loan detections appearing? |\n")
    f.write("| T+48h | Full station audit — run loan classifier on new data |\n")
    f.write("| T+48h | Decision: keep, watch, or rotate each station |\n")

print("✅ exports/station_rotation_commands.md", flush=True)

print(f"\n{'='*60}")
print(f"FINAL SUMMARY")
print(f"{'='*60}")
print(f"  ✅ Keep (4): KTRH, KLIF, WSB, WBAP")
print(f"  🆕 Add (3): KLBJ (Austin), WGUL (Tampa), KABC (LA)")
print(f"  ⏸️ Pause (6): WOAI, WWTN, WHBO, WTAM, WIBC (+KABC disabled but being added back)")
print(f"  ❌ Cannot add: WLW, KNTH, KTSA, WFLA — not in config/stations.yaml")
print(f"\n  Total active for 48h: 7 stations ({' + '.join(b[1] for b in batch if b[0]!='pause')})")
