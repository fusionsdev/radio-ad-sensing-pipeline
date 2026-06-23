# Station Config Change Plan

**Generated**: 2026-06-21

## Changes to `config/stations.yaml`

### 1. Enable These Stations (set `enabled: true`)

```yaml
  - name: klbj-am-590
    display_name: "KLBJ 590 AM — Austin, TX"
    url: http://playerservices.streamtheworld.com/pls/KLBJAMAAC.pls
    format: aac
    enabled: true  # ADDED for 48h loan batch — ffprobe verified

  - name: kabc-am-790
    display_name: "KABC 790 AM — Los Angeles, CA"
    url: http://playerservices.streamtheworld.com/api/livestream-redirect/KABCAM.mp3
    format: mp3
    enabled: true  # ADDED for 48h loan batch — ffprobe verified
```

### 2. Add New Stations

Insert these entries into the appropriate market sections:

```yaml
  # --- Ohio (Cincinnati) ---
  - name: wlw-700
    display_name: "WLW 700 AM — Cincinnati, OH"
    url: https://stream.revma.ihrhls.com/zc1713
    format: aac
    enabled: true  # ADDED for 48h loan batch — iHeart AAC verified

  # --- Texas (Houston) — 2nd station ---
  - name: knth-1070
    display_name: "KNTH 1070 AM — Houston, TX"
    url: http://playerservices.streamtheworld.com/api/livestream-redirect/KNTHAM.mp3
    format: mp3
    enabled: true  # ADDED for 48h loan batch — StreamTheWorld MP3 verified

  # --- Texas (San Antonio) — replace WOAI ---
  - name: ktsa-550
    display_name: "KTSA 550 AM — San Antonio, TX"
    url: http://live.amperwave.net/direct/alphacorporate-ktsaamaac-imc3?source=iheart
    format: aac
    enabled: true  # ADDED for 48h loan batch — AmperWave AAC verified

  # --- Florida (Tampa) — replace WGUL ---
  - name: wfla-970
    display_name: "WFLA 970 AM — Tampa, FL"
    url: https://stream.revma.ihrhls.com/zc2823
    format: aac
    enabled: true  # ADDED for 48h loan batch — iHeart AAC verified
```

### 3. Disable These Stations (set `enabled: false`)

```yaml
  - name: woai-am-1200
    enabled: false  # PAUSED — 48h loan batch rotation. Replace by KTSA.

  - name: wwtn-fm-997
    enabled: false  # PAUSED — 48h loan batch rotation. Weak loan signal.

  - name: whbo-1040
    enabled: false  # PAUSED — 48h loan batch rotation. Replace by WFLA.

  - name: wibc-fm-931
    enabled: false  # PAUSED — 48h loan batch rotation. Freeing slot.

  - name: wtam-am-1100
    enabled: false  # PAUSED — 48h loan batch rotation. 0 loan ads.
```

### 4. Keep Enabled (no change needed)

```yaml
  - name: klif-am-570   # 12 loan ads — keep
  - name: wbap-am-820   # 13 loan ads — keep
  - name: ktrh-am-740   # 10 loan ads — keep
  - name: wsb-am-750    # 15 loan ads — keep
```

## Docker Commands

### Apply Config and Restart

```bash
# Rebuild and restart ingestor with new station config
docker compose up -d --force-recreate ingestor

# Check ingestor is picking up all 10 stations
docker compose logs ingestor --tail 50
```

### Post-Restart Verification (after 15 minutes)

```bash
# Check chunk production per station
docker compose exec worker sqlite3 /app/data/pipeline.db "
  SELECT s.name, COUNT(c.id) as chunks
  FROM chunks c JOIN stations s ON s.id = c.station_id
  WHERE c.created_at > datetime('now', '-1 hour')
  GROUP BY s.name ORDER BY chunks DESC;
"
```

### 48h Evaluation

```bash
# Check loan detections after 48h
docker compose exec worker python /tmp/loan_audit.py
```

## Rollback Plan

If any new stream fails in Docker (empty chunks, 403, etc.):

1. Set that station to `enabled: false`
2. Re-enable the corresponding paused station
3. Restart ingestor: `docker compose up -d --force-recreate ingestor`

| New Station | Rollback To |
|---|---|
| KTSA (San Antonio) | WOAI |
| WFLA (Tampa) | WHBO |
| KLBJ (Austin) | (no rollback — new market) |
| WLW (Cincinnati) | (no rollback — new market) |
| KNTH (Houston) | (no rollback — 2nd HOU) |
| KABC (Los Angeles) | (no rollback — LA was already disabled) |
