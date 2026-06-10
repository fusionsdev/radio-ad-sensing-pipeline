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

## Adding a new station's stream URL

Most US talk/news/sports stations hit one of three discovery layers, in this
order of preference:

1. **iHeart / Triton public HLS** — `https://stream.revma.ihrhls.com/zc<id>/hls.m3u8`, where `<id>` is the trailing integer in the iHeart live page URL. Works for 100% of iHeart-owned stations, no auth.
2. **iHeart `live-meta` API → real AmperWave URL** — for Audacy-mirrored stations (post June 2025 deal), the iHeart mirror page's underlying `https://us.api.iheart.com/api/v3/live-meta/stream/<id>/station-meta` endpoint leaks the actual `live.amperwave.net/direct/audacy-<call>aac-imc` URL.
3. **Owner-specific CDNs** — Cox (StreamGuys), Nexstar (AmperWave no `audacy-` prefix), Cumulus, Curtis (Triton embed).

Full discovery ladder, owner-by-owner mountpoint table, capture scripts,
and the 2026-06-11 verified-PASS list → `references/station-stream-urls.md`.

If a new station's URL keeps 5XX'ing, the AmperWave edge is rate-limiting
server-side — open the station's Audacy listen page in a real browser once
to warm the session, then reuse the URL. Don't hammer AmperWave direct
endpoints from a cron without 8s+ between probes.

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
| `config/loan_keywords.yaml` | **35** loan/funding phrases for worker scan — list of `{phrase, confidence}` dicts (NOT a flat string list) |
| `config/cfpb_collector.yaml` | CFPB batch collector (states, products, API/CSV mode) |
| `config/trademark.yaml` | Trademark bridge thresholds + keyword variants |
| `.env` | `TELEGRAM_BOT_TOKEN` / `CHAT_ID` for **pipeline alerter only** |

## Enabled stations (check live file)

```powershell
docker exec radio-ingestor python -c "from shared.config import load_stations; print([s.name for s in load_stations() if s.enabled])"
```

Operator may enable many stations; **one GPU worker** ~1 chunk/min → backlog grows if ingest >> process. Suggest reducing `enabled` in `stations.yaml` + restart ingestor if user wants queue to drain.

## Keyword watchlist

Loaded from `config/loan_keywords.yaml` — **list of `{phrase: str, confidence: float}` dicts**, not a flat string list. The skill examples below show the right way to load it; iterating as `for kw in kws` gives you **dicts**, not strings. Phrases cover: hard money, business funding, reverse mortgage, debt consolidation, cash advance, title loan, payday loan, refinance, same-day funding, home equity, HELOC, personal loan, small business loan, merchant cash advance, debt relief, tax relief, timeshare exit, life insurance, etc.

> 📚 Full corpus verdict (per-keyword hit count, normalized probe, ban list, 2026-06-11 verified data) → `references/keyword-curation.md`.

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

## CFPB trademark seed collector (batch — not radio ingest)

Supplemental source for **Trademark Keyword Research Layer**. CFPB complaints → reviewable brand/company seeds. **Not proof of radio advertising.** Never auto-approved.

| Item | Value |
|------|-------|
| Config | `config/cfpb_collector.yaml` |
| Docs | `docs/cfpb-complaint-collector.md` |
| Dashboard | `/cfpb`, `/cfpb/candidates` |
| Tables | `cfpb_*`, `trademark_*` (migrations 006–007) |

Run collector:

```powershell
.\scripts\run-cfpb-collector.ps1              # host .venv
.\scripts\run-cfpb-collector.ps1 -Docker      # docker compose --profile cfpb run --rm cfpb-collector
docker exec radio-worker python -m collectors.cfpb_complaints_collector   # after worker image rebuild
```

Query CFPB stats (live DB):

```powershell
docker exec radio-worker python -c "
import sqlite3
c=sqlite3.connect('/app/data/pipeline.db')
for t in ('cfpb_complaints_raw','cfpb_company_entities','cfpb_brand_candidates'):
  try: print(t, c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
  except: print(t, 'n/a')
r=c.execute('SELECT status,finished_at FROM cfpb_collection_runs ORDER BY id DESC LIMIT 1').fetchone()
print('last_run', r)
c.close()
"
```

Export CSV: `python scripts/export_cfpb_brand_candidates.py --min-score 70`

**Ask before:** running collector against production DB during heavy worker load (SQLite write contention — prefer low-traffic window).

## Common log signals

| Log | Meaning |
|-----|---------|
| `fpcalc` FileNotFoundError | Chromaprint missing in image — **non-fatal**, ASR continues |
| `chunk transcribed` | ASR done; check if LLM/dedup after |
| `extraction/dedup failed` | Chunk → `dropped` |
| ingestor `enqueue` / retry | Normal; station stream hiccups |

## ⚠️ Pitfalls (Windows + Docker host)

1. **MSYS bash auto-translates `/tmp/...` paths inside `docker exec`** — you'll see errors like `python: can't open file '/app/H:/Cache/Temp/probe.py'`. Three reliable workarounds:
   - Pass the script as a single-quoted `-c` arg via `docker exec radio-worker python -c '<script>'` (works for short scripts; use `subprocess.run` from `execute_code` for long ones to dodge the 5-min / 50KB tool limits).
   - `docker cp` from a **container-side** `/tmp/...` (don't use host `/tmp/...`).
   - Run the script through the host `.venv` against a non-prod DB: `.venv\Scripts\python scripts\probe.py` (read-only, doesn't affect Docker).
   **Do NOT** `docker exec -i radio-worker sh -c 'cat > /tmp/foo.py' < /tmp/foo.py` — the `<` redirect inherits the same MSYS path mangling.

2. **PowerShell wrapper scripts (`*.ps1`) mis-execute under MSYS bash** — `.\scripts\pipeline-status.ps1` runs but emits `= command not found` / `syntax error near unexpected token '('` because MSYS re-parses the script. Either invoke via `pwsh -ExecutionPolicy Bypass -File ...` or accept the harmless stderr; the script still produces correct output (verified 2026-06-11).

3. **`docker exec` is foreground-only** — never background a long query with `&`. If the query exceeds terminal timeout, run from `execute_code` (which has its own 5-min ceiling) or write the result to a container-side file and tail it.

4. **Reading `data/pipeline.db` from the Windows host** is fine for **debugging the schema** (PRAGMA, joins, list of ad_categories) — the "stale snapshot" caveat only applies when ingest is actively writing and you compare counts vs live `radio-worker`. For status/queue numbers, always query inside `radio-worker`.

## ⚠️ `keyword_hits = 0` does NOT mean the scanner is broken

The worker scans `transcripts.text` (raw ASR output) with substring matching against `config/loan_keywords.yaml`. It does **not** look at `detections.ad_category`. So `keyword_hits=0` is almost always one of:

1. **Keyword list drift** — `loan_keywords.yaml` was written for a category mix that doesn't match the live corpus. Fastest diagnosis: pick the top 3 ad_category values from `detections` and `grep` transcripts for any keyword in the list. If yield = 0 across the whole file, the list is stale.
2. **The scanner genuinely has nothing to do** — e.g. ingest is paused, only news chunks flowing.
3. **Schema confusion** — operator is querying the wrong table or wrong container. Always query inside `radio-worker` (see Windows DB caveat above).

Probe recipe (live, uses real YAML shape — `kws` is a list of dicts):

```powershell
docker exec radio-worker python -c "
import sqlite3, yaml
c=sqlite3.connect('/app/data/pipeline.db')
kws=yaml.safe_load(open('/app/config/loan_keywords.yaml'))['keywords']
phrases=[k['phrase'] for k in kws]            # <- IMPORTANT: extract 'phrase' field
rows=c.execute('SELECT d.ad_category, t.text FROM detections d JOIN transcripts t ON t.chunk_id=d.chunk_id').fetchall()
hits={p:0 for p in phrases}
for cat,text in rows:
  tl=(text or '').lower()
  for p in phrases:
    if p.lower() in tl: hits[p]+=1
print('hits per keyword over', len(rows), 'detection transcripts:')
for p,v in sorted(hits.items(), key=lambda x:-x[1]):
  pct=v/len(rows)*100 if rows else 0
  flag='DEAD' if v==0 else ('RARE<1%' if pct<1 else 'OK')
  print(f'  {p:30s} {v:5d} {pct:6.2f}%  {flag}')
c.close()
"
```

### Distinguishing "DEAD keyword" from "ASR artifact"

A 0-hit keyword can mean two very different things:

1. **The phrase never appears in the corpus** (e.g. corpus is Texas talk radio with roofing/mattress ads, no loan funders). → safe to ban the keyword.
2. **ASR mis-renders the phrase** (e.g. `unfiled tax returns` written correctly, but `wage garnishment` always gets a comma inserted, or `irs` is misheard as part of `U.S.`). → don't ban — fix the phrase.

To distinguish, also probe a **normalized** corpus (strip non-alnum). If a keyword still gets 0 hits after normalization, the content isn't there. If a known-true phrase (e.g. `unfiled tax returns`) hits 9× in raw AND normalized, you've confirmed ASR is fine and the dead list is just genuinely dead.

```powershell
docker exec radio-worker python -c "
import sqlite3, re
c=sqlite3.connect('/app/data/pipeline.db')
# pick a known-true tax-relief transcript and look for 'irs tax debt' vs 'u.s. tax'
sample=c.execute(\"SELECT t.text FROM transcripts t JOIN detections d ON d.chunk_id=t.chunk_id WHERE d.ad_category='tax_relief' LIMIT 1\").fetchone()
print(repr(sample[0])[:500])
c.close()
"
```

Common ASR corruption to expect: `U.S.` (with dots) breaks substring `irs`, `garnish your paycheck` ≠ `garnish paycheck` (possessive inserts), `home equity line of credit` ≠ `home equity line`. Spot-check 1 transcript per category before banning.

### Banning keywords — review-before-edit workflow

When the operator says "ban unrelated keywords, send for review" / "แบน keyword ที่ไม่เกี่ยวข้อง":

1. **Compute per-keyword hit count** (probe above) → bucket into ✅ OK / 🟡 rare / ❌ DEAD.
2. **Cross-reference DEAD keywords against `detections.ad_category`** — if the DEAD keyword's *expected* ad_category is **missing from the corpus entirely** (e.g. `reverse_mortgage`, `timeshare_exit`), the keyword is targeting a category that never airs. Strong ban candidate.
3. **Sample 1 transcript from each top-3 ad_category** to confirm ASR fidelity (see "Distinguishing" above).
4. **Present a "Keep / Ban" table** to the operator with: keyword, hits, %transcripts, matching ad_category, sample snippet. **Do not edit `loan_keywords.yaml` until operator confirms** (matches the "Ask before" rule).

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
