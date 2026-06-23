# Final 48h Batch Startup Report

**Generated**: 2026-06-21
**Status**: ⚠️ Config applied — Docker restart required

## Station Config Applied

All 10 enabled / 6 disabled changes have been applied to `config/stations.yaml`.

### Enabled Stations

| # | Station | Market | Format | Stream URL | Verified |
|---|---|---|---|---|---|
| 1 | KTRH | Houston, TX | Talk | `http://stream.revma.ihrhls.com/zc2285` | ✅ ffprobe AAC |
| 2 | KLIF | Dallas, TX | Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KLIFAM.mp3` | ✅ ffprobe MP3 |
| 3 | WSB | Atlanta, GA | News/Talk | `http://oom-cmg.streamguys1.com/atl750/atl750-sgplayer-mp3` | ✅ ffprobe MP3 |
| 4 | WBAP | Dallas–Fort Worth, TX | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/WBAPAM.mp3` | ✅ ffprobe MP3 |
| 5 | KLBJ | Austin, TX | News/Talk | `http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls` | ✅ ffprobe PLS resolves |
| 6 | WLW | Cincinnati, OH | News/Talk | `https://stream.revma.ihrhls.com/zc1713` | ✅ ffprobe AAC |
| 7 | KNTH | Houston, TX | News/Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KNTHAM.mp3` | ✅ ffprobe MP3 |
| 8 | KTSA | San Antonio, TX | News/Talk | `http://live.amperwave.net/direct/alphacorporate-ktsaamaac-imc3?source=iheart` | ✅ ffprobe AAC |
| 9 | WFLA | Tampa, FL | News/Talk | `https://stream.revma.ihrhls.com/zc2823` | ✅ ffprobe AAC |
| 10 | KABC | Los Angeles, CA | Talk | `http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3` | ✅ ffprobe MP3 |

### Disabled Stations

| Station | Previous Status | Reason |
|---|---|---|
| WOAI | enabled → disabled | Replaced by KTSA (San Antonio) |
| WWTN | enabled → disabled | Weak loan signal (1 unique) |
| WHBO | enabled → disabled | Replaced by WFLA (Tampa) |
| WIBC | enabled → disabled | Freeing slot |
| WTAM | enabled → disabled | 0 loan ads |
| WGUL | disabled (no change) | 403 Forbidden — stream dead |

## Action Required: Docker Restart

The sandbox does not have permission to restart Docker containers.

**You must run this command to pick up the new config:**

```bash
docker compose restart ingestor
```

Or to also apply any image changes:

```bash
docker compose up -d --force-recreate ingestor
```

### What happens after restart

| Time | Event |
|---|---|
| T+0 | Ingestor reads `config/stations.yaml`, populates DB `stations` table |
| T+1min | All 10 stations start producing 90s chunks |
| T+15min | ~60-100 chunks per station |
| T+30min | First transcripts created from processed chunks |
| T+60min | Full pipeline flow: chunk → ASR → detection |
| T+48h | Run loan classifier audit on new data |

### Verification commands (run after restart)

```bash
# 1. Check all 10 stations are in DB
docker compose exec worker python -c "
import sqlite3
conn = sqlite3.connect('/app/data/pipeline.db')
c = conn.cursor()
c.execute('select name from stations where enabled=1 order by name')
for r in c.fetchall(): print(r[0])
conn.close()
"

# 2. Check chunk production (after 15 min)
docker compose exec worker sqlite3 /app/data/pipeline.db "
  SELECT s.name, COUNT(c.id) as chunks
  FROM chunks c JOIN stations s ON s.id = c.station_id
  WHERE c.created_at > datetime('now', '-1 hour')
  GROUP BY s.name ORDER BY chunks DESC;
"

# 3. Check transcripts (after 30 min)
docker compose exec worker sqlite3 /app/data/pipeline.db "
  SELECT s.name, COUNT(t.id) as transcripts
  FROM transcripts t
  JOIN chunks c ON c.id = t.chunk_id
  JOIN stations s ON s.id = c.station_id
  WHERE t.id > (SELECT MAX(id) - 1000 FROM transcripts)
  GROUP BY s.name ORDER BY transcripts DESC;
"

# 4. Check for empty_chunk loops
docker compose logs ingestor --tail 50 | grep -i "empty\|error\|warn"

# 5. Check live DB freshness
docker compose exec worker sqlite3 /app/data/pipeline.db "
  SELECT 'detections', COUNT(*), MAX(id) FROM detections
  UNION ALL SELECT 'transcripts', COUNT(*), MAX(id) FROM transcripts
  UNION ALL SELECT 'chunks_done', COUNT(*), MAX(id) FROM chunks WHERE status='done';
"
```

## Monitoring Schedule

| Check | Cadence | Command |
|---|---|---|
| Station health | Every 1h | `docker compose ps` |
| Chunk production | Every 1h | Verify all 10 stations producing |
| Loan detections | Every 4h | Check for `true_loan` classification |
| Full audit | T+48h | `python scripts/loan_audit.py` |
