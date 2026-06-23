# Station Rotation Commands

**Generated**: 2026-06-21 05:43

## Config Changes Required

Edit `config/stations.yaml`:

### Enable (set to `enabled: true`)

```yaml
  - name: klbj-am-590
    enabled: true  # ADDED for 48h loan batch
  - name: wgul-860
    enabled: true  # ADDED for 48h loan batch
  - name: kabc-am-790
    enabled: true  # ADDED for 48h loan batch
```

### Keep Enabled (already `enabled: true`)

```yaml
  - name: ktrh-am-740  # KEEP — 10 loan ads
  - name: klif-am-570  # KEEP — 12 loan ads
  - name: wsb-am-750  # KEEP — 15 loan ads
  - name: wbap-am-820  # KEEP — 13 loan ads
```

### Disable (set to `enabled: false`)

```yaml
  - name: woai-am-1200  # PAUSE — 3 loan ads (loan batch rotation)
  - name: wwtn-fm-997  # PAUSE — 2 loan ads (loan batch rotation)
  - name: whbo-1040  # PAUSE — 2 loan ads (loan batch rotation)
  - name: wtam-am-1100  # PAUSE — 0 loan ads (loan batch rotation)
  - name: wibc-fm-931  # PAUSE — 5 loan ads (loan batch rotation)
```

## Rebuild and Restart

After editing `config/stations.yaml`:

```bash
docker compose up -d --force-recreate ingestor
```

## Verification Commands

```bash
# Check ingestor is running all 10 stations
docker compose logs ingestor --tail 50

# Check chunk production (after 15min)
docker compose exec worker sqlite3 /app/data/pipeline.db "
  SELECT s.name, COUNT(c.id) as chunks
  FROM chunks c JOIN stations s ON s.id = c.station_id
  WHERE c.created_at > datetime('now', '-1 hour')
  GROUP BY s.name ORDER BY chunks DESC;
# Check loan detections after 48h
docker compose exec worker python /tmp/loan_audit.py
```

## 48h Evaluation Timeline

| Time | Action |
|---|---|
| T+0h | Apply config changes, restart ingestor |
| T+1h | Verify all 10 streams producing chunks |
| T+24h | Quick check — any loan detections appearing? |
| T+48h | Full station audit — run loan classifier on new data |
| T+48h | Decision: keep, watch, or rotate each station |
