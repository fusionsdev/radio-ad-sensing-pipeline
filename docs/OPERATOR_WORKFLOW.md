# Operator Workflow — Radio Ad-Sensing Pipeline

## Consumer personal loan classifier rollout

**Classifier:** `consumer_personal_loan_v1`  
**Taxonomy:** `2026-06-19`  
**Config:** `config/consumer_personal_loan_taxonomy.yaml`, `config/vertical_keywords.yaml`

### What changed

- `keyword_hits` persists **accept-only** consumer personal loan intent.
- Legacy tax / insurance / business / mortgage hits are no longer scanned.
- Worker logs structured classifier events and periodic rollout summaries.

### Deployment

| Change type | Action | Effective when |
|---|---|---|
| Taxonomy YAML edits | Save file (bind-mounted) | Next transcribed chunk |
| Python code changes | Rebuild worker image | After container restart |

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml build worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d worker
```

Config under `./config` is read-only mounted into containers — **no rebuild needed for YAML-only changes**.

### Post-deploy smoke (30–60 minutes)

1. Confirm worker is healthy:
   ```powershell
   docker logs radio-worker --tail 40
   ```

2. Watch classifier logs:
   ```powershell
   docker logs radio-worker 2>&1 | Select-String "keyword classifier"
   ```

   Expect structured fields:
   - `classifier_name`, `classifier_version`, `taxonomy_version`
   - `classifier_status`, `classifier_reason`
   - Rollout summary every 50 transcribed chunks with `target_phrase_matches`, `accepted_keyword_hits`, `rejected_after_classifier`, `top_rejection_reasons`

3. Inspect keyword hits (via worker container — do not read bind-mounted DB from Windows host during ingest):
   ```powershell
   docker exec radio-worker python -c "import sqlite3; c=sqlite3.connect('/app/data/pipeline.db'); print(c.execute('SELECT keyword, COUNT(*) n FROM keyword_hits GROUP BY keyword ORDER BY n DESC LIMIT 20').fetchall()); c.close()"
   ```

### Legacy keyword_hits cleanup

Audit polluted rows **before** trusting dashboard keyword stats:

```powershell
# Dry-run (default — no deletes)
docker exec radio-worker python scripts/audit_keyword_hits_verticals.py --db /app/data/pipeline.db

# Delete flagged rows after operator review
docker exec radio-worker python scripts/audit_keyword_hits_verticals.py --db /app/data/pipeline.db --apply
```

Or on host venv:

```powershell
.venv\Scripts\python scripts/audit_keyword_hits_verticals.py --db data/pipeline.db
```

Flagged examples: `tax relief`, `back taxes`, `term life insurance`, `business funding`, generic `loan`.

### Classifier metadata in DB (optional)

`keyword_hits` has no classifier metadata columns today. Recommended manual migration:

`docs/recommended-migrations/022_keyword_hits_classifier_metadata.sql`

Until applied, version fields appear in **worker logs only**.

### Telegram periodic report (every 3 hours)

`radio-alerter` pushes a pipeline + keyword summary when enabled in `config/settings.yaml`:

```yaml
alerter_periodic_report_enabled: true
alerter_periodic_report_hours: 3
```

Requires `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Restart alerter after config change:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d --no-deps alerter
```

Manual one-shot (copy script — not in image):

```powershell
docker cp scripts/pipeline_telegram_report.py radio-alerter:/tmp/pipeline_telegram_report.py
docker exec radio-alerter python /tmp/pipeline_telegram_report.py --db /app/data/pipeline.db
docker exec radio-alerter python /tmp/pipeline_telegram_report.py --db /app/data/pipeline.db --dry-run
```

Hermes operator context: `.hermes.md` (auto-loaded by Hermes gateway).

### Ambiguous transcripts

Phrases like `funding available` or `financing options` are **not** in target scan phrases — they never reach the classifier and **never write** `keyword_hits`. There is no keyword review queue; `review` classifier outcomes are logged but not persisted.

### Dashboard

After rollout smoke: `http://127.0.0.1:8081` → Keyword hits / verticals (`consumer-personal-loan`).

Run legacy audit first if dashboard still shows tax/insurance keywords from pre-rollout data.
