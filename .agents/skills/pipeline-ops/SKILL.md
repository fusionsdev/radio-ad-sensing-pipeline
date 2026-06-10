---
name: pipeline-ops
description: >-
  Remote operator for the radio ad-sensing pipeline — status, queue, stations,
  keywords, Docker health. Use when user asks about pipeline, stations, queue,
  keyword hits, scorecard, ingestor, worker, ads, or radio-ad-sensing-pipeline
  from Telegram/Hermes/CLI. Trigger: /pipeline-ops
argument-hint: "[status|queue|stations|keywords|logs worker|logs ingestor]"
---

# Pipeline Ops — Radio Ad-Sensing Pipeline

Operator skill for **Hermes gateway (Telegram)** and CLI. Read `AGENTS.md` and `PLAN.md` for architecture; this skill is the **runbook**.

## Project root

```
h:\DEV\projects\radio-ad-sensing-pipeline
```

Set terminal `cwd` here before any command.

## What this system is

24/7 local pipeline: ingest U.S. talk-radio streams → 90s WAV chunks → faster-whisper ASR → Ollama/Qwen LLM extraction → fuzzy dedup → SQLite → Telegram alerter (push) + FastAPI dashboard (read-only).

**There is no Redis.** Queue = SQLite `chunks` table (`pending` / `processing` / `done` / `dropped`).

## Docker stack (production on this host)

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
docker compose ps
```

| Container | Role |
|-----------|------|
| `radio-ingestor` | ffmpeg per enabled station → enqueue chunks |
| `radio-worker` | ASR + LLM + dedup + keyword scan |
| `radio-alerter` | Outbound Telegram alerts (separate from Hermes bot) |
| `radio-dashboard` | FastAPI UI — host port **8081** (windows-dev overlay) |
| `radio-ollama` | Local LLM |
| `radio-prometheus` / `radio-grafana` | Metrics |

Full Win GPU stack:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml ps
```

## CRITICAL — Windows Docker DB reads

**Never trust `data/pipeline.db` read directly from the Windows host** during active Docker ingest. Bind-mount sync can show a **stale** snapshot (small file, old pending counts).

**Always query live DB inside the worker container:**

```powershell
docker exec radio-worker python -c "import sqlite3; c=sqlite3.connect('/app/data/pipeline.db'); print(c.execute('SELECT status, COUNT(*) FROM chunks GROUP BY status').fetchall()); c.close()"
```

Or pipe the query script:

```powershell
Get-Content scripts\pipeline_status_query.py -Raw | docker exec -i radio-worker python -
# or wrapper:
.\scripts\pipeline-status.ps1
```

## ⚠️ DB schema gotchas (verified 2026-06-11)

Skill examples and `AGENTS.md` mention column names that **do not match the live schema**. Always probe before assuming:

```powershell
docker exec radio-worker python -c "import sqlite3; c=sqlite3.connect('/app/data/pipeline.db'); [print(r) for r in c.execute('PRAGMA table_info(chunks)').fetchall()]; c.close()"
```

Known mismatches (use these names, not the ones in old docs):

| Table | Wrong (old doc) | Right (live) |
|---|---|---|
| `chunks` | `ingest_ts`, `started_at` | `start_ts`, `end_ts` |
| `detections` | `category`, `station_id` | `ad_category`, `chunk_id` (join `chunks` for station) |
| `keyword_hits` | (n/a) | `station_id` lives here, not on `detections` |

Canonical queries → `references/db-schema.md` (copy-paste ready, including per-station health, detection mix, top advertisers, and the `keyword_hits=0` heuristic).

## ⚠️ Ollama container has no shell tools

`radio-ollama` is a minimal `ollama/ollama` image — **no `curl` / `wget` / `python`**. To probe the LLM service, run from another container on the same network:

```powershell
docker exec radio-worker python -c "
import urllib.request, json
d=json.loads(urllib.request.urlopen('http://radio-ollama:11434/api/tags', timeout=5).read())
for m in d.get('models', []): print(m.get('name'), m.get('size'))
"
```

## Quick status (run every diagnostic)

```powershell
.\scripts\pipeline-status.ps1
docker compose ps
docker logs radio-worker --tail 15
docker logs radio-ingestor --tail 15
```

## Config paths

| File | Purpose |
|------|---------|
| `config/stations.yaml` | Station URLs; `enabled: true` = live ingest |
| `config/settings.yaml` | `db_path`, chunk length, dedup, thresholds |
| `config/loan_keywords.yaml` | 15 loan/funding keywords for worker scan |
| `.env` | `TELEGRAM_BOT_TOKEN` / `CHAT_ID` for **pipeline alerter only** |

## Enabled stations (check live file)

```powershell
docker exec radio-ingestor python -c "from shared.config import load_stations; print([s.name for s in load_stations() if s.enabled])"
```

Operator may enable many stations; **one GPU worker** ~1 chunk/min → backlog grows if ingest >> process. Suggest reducing `enabled` in `stations.yaml` + restart ingestor if user wants queue to drain.

## Keyword watchlist

Loaded from `config/loan_keywords.yaml` — hard money, business funding, reverse mortgage, debt consolidation, cash advance, title loan, payday loan, refinance, same-day funding, home equity, HELOC, personal loan, small business loan, merchant cash advance, debt relief.

Query hits (live DB):

```powershell
docker exec radio-worker python -c "
import sqlite3
c=sqlite3.connect('/app/data/pipeline.db')
rows=c.execute('SELECT keyword, COUNT(*) n FROM keyword_hits GROUP BY keyword ORDER BY n DESC LIMIT 15').fetchall()
print(rows)
c.close()
"
```

## Dashboard equivalents (SQL source: `dashboard/queries.py`)

- **Overview** — chunks/detections today, queue depth, station health
- **Scorecard** — 7d yield = keyword_hits ÷ chunks per station
- **Keywords** — station × keyword matrix
- **Ads** — `canonical_ads` deduplicated advertisers

Local dashboard: `http://127.0.0.1:8081` (when compose up).

## Common log signals

| Log | Meaning |
|-----|---------|
| `fpcalc` FileNotFoundError | Chromaprint missing in image — **non-fatal**, ASR continues |
| `chunk transcribed` | ASR done; check if LLM/dedup after |
| `extraction/dedup failed` | Chunk → `dropped` |
| ingestor `enqueue` / retry | Normal; station stream hiccups |

## ⚠️ `keyword_hits = 0` does NOT mean the scanner is broken

The worker scans `transcripts.text` (raw ASR output) with substring matching against `config/loan_keywords.yaml`. It does **not** look at `detections.ad_category`. So `keyword_hits=0` is almost always one of:

1. **Keyword list drift** — `loan_keywords.yaml` was written for a category mix that doesn't match the live corpus. Fastest diagnosis: pick the top 3 ad_category values from `detections` and `grep` transcripts for any keyword in the list. If yield = 0 across the whole file, the list is stale.
2. **The scanner genuinely has nothing to do** — e.g. ingest is paused, only news chunks flowing.
3. **Schema confusion** — operator is querying the wrong table or wrong container. Always query inside `radio-worker` (see Windows DB caveat above).

Probe recipe:

```powershell
docker exec radio-worker python -c "
import sqlite3, yaml
c=sqlite3.connect('/app/data/pipeline.db')
kws=yaml.safe_load(open('/app/config/loan_keywords.yaml'))['keywords']
rows=c.execute('SELECT d.ad_category, t.text FROM detections d JOIN transcripts t ON t.chunk_id=d.chunk_id LIMIT 50').fetchall()
hits={kw:0 for kw in kws}
for cat,text in rows:
  for kw in kws:
    if kw.lower() in (text or '').lower(): hits[kw]+=1
print('hits per keyword over', len(rows), 'loan-adjacent transcripts:')
for k,v in hits.items(): print(f'  {k:30s} {v}')
c.close()
"
```

If all zeros → the list is dead and needs curation from corpus bigrams. If non-zero but `keyword_hits` table is still empty → ingestion pipeline hasn't reached those chunks yet (check `pending`/`processing` and worker logs).

## Hermes vs pipeline Telegram

| Bot | Purpose |
|-----|---------|
| **Hermes gateway** | Interactive Q&A (this skill) |
| **Pipeline alerter** | Auto push: new ads, station down, digest |

Same or separate bot tokens OK; alerter only sends, Hermes polls.

## Safe actions (read-only)

- `docker compose ps`, `docker logs`, `pipeline-status.ps1`
- Read `config/`, `plan/`, `AGENTS.md`, `dashboard/queries.py`
- `pytest` (local `.venv`) — does not affect production DB

## Ask before doing

- Edit `config/stations.yaml` (enable/disable streams)
- `docker compose down`, restart services, drop chunks
- Edit production `data/pipeline.db`
- Commit/push git changes
- Read or print `.env` secrets

## Tests & migrate

```powershell
.venv\Scripts\pytest -q
.venv\Scripts\python -c "from shared.db import migrate; migrate('data/test.db')"
```

## Response format (Telegram)

Keep answers short. Prefer:

1. One-line health verdict (OK / degraded / backlog)
2. Bullet metrics (queue by status, enabled stations, worker activity)
3. One recommended action if degraded

Example:

```
Pipeline: DEGRADED — backlog
• pending 4200 / done 990 / dropped 2
• 9 stations ingesting, 1 worker ~1 chunk/min
• Worker active (chunk ~1000 ASR ok); fpcalc warnings benign
→ To drain: disable extra stations in stations.yaml, restart ingestor
```
