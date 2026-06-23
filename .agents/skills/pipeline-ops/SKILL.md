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

## Memory OS preload (startup)

On `/pipeline-ops` invocation, load before any ops query:

```txt
AGENTS.md
project-memory/00_Project_Overview.md
project-memory/01_Current_Architecture.md
project-memory/02_Operating_Policy.md
project-memory/03_Forbidden_Assumptions.md
project-memory/04_Agent_Load_Order.md
```

Contract: `config/agent-memory-contract.md` · Obsidian MCP: `config/obsidian-mcp.json`

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

## Keyword watchlist

Loaded from `config/loan_keywords.yaml` — hard money, business funding, reverse mortgage, debt consolidation, cash advance, title loan, payday loan, refinance, same-day funding, home equity, HELOC, personal loan, small business loan, merchant cash advance, debt relief.

Query hits (live DB):

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

## Justia Trademark Integration (updated 2026-06-17)

See `references/justia-trademark-loan-workflow.md` (full spec, filters, scoring, policy, CLI, pitfalls, browser verification protocol).

**Browser Verification Agent Workflow (new class-level pattern from latest sessions)**:
- Primary page: https://trademarks.justia.com/category/insurance-and-financial/
- Target specific visible candidates only: LOAN COMMAND (must show "bank loan pricing" or equivalent), LOAN REPLAY ("loan services"), LOAN MAX ("title loans").
- Strict include terms: loan, loans, lending, lender, borrower, personal loan, installment loan, cash advance, consumer loan, loan financing, financing loans.
- Strict rejects: mortgage-only, debt relief, debt consolidation, SBA, credit repair, insurance, investment, wealth management, real estate, crypto, payment processing, etc.
- Critical: Do not invent URLs. Only use URLs from loaded browser address bar after navigation. Do not infer marks from serials. If Cloudflare blocks any detail page, stop immediately, report actual verified count (often 0), list blocked_pages, do not bypass.
- Save verified detail pages as HTML to `data/manual/2026-06-17-loan-only/{sanitized-mark}_{serial}.html`.
- Stop exactly at user-specified target (e.g. 3 for test batch, 7 for smoke). Never pad with guesses.
- After saves, run the import command: `cd H:\\DEV\\projects\\ppc_project\\justia-miner && .\\.venv\\Scripts\\python.exe scripts\\collect_justia_trademarks.py --import-detail-dir data\\manual\\2026-06-17-loan-only --db data\\justia.db --csv data\\exports\\2026-06-17-loan-only --sync-pipeline`

**USPTO Verification Fallback (scaling solution for Cloudflare blocks)**:
When Browser Verification Agent is blocked by Cloudflare on Justia detail pages:
1. Use Apify Google SERP discovery (`scripts/discover_justia_via_apify.py`) with recall-first queries (site:trademarks.justia.com "loan services" style, minimal negatives).
2. Run `scripts/verify_apify_candidates_uspto.py` on the accepted CSV to extract serials, query official USPTO/TSDR for word_mark, owner, goods_services, status.
3. Re-apply strict loan-only filter on *official* goods_services text (not Apify snippet).
4. Output verified candidates with uspto_verified, verification_status, conservative flags (keyword_allowed=true only on strong loan match, ad_copy_allowed=false, landing_page_allowed=false, review_status=needs_review).
5. Manual HTML save + collect script still required for final pipeline import. Never auto-approve.

This pattern (Apify discovery → USPTO serial verification → manual verification → import) is the durable workflow for scaling Justia loan trademark corpus under Cloudflare constraints.

**Name-Only Collector Mode (v2 — 2026-06-18 operator preference for maximum volume)**:
When operator says "do not want deep verification right now", "only wants to collect as many potential trademark/brand names as possible", "scale discovery volume", "simplify to name-only", or shows frustration with Cloudflare/browser blocks:
- Use `scripts/discover_justia_names_via_apify.py` (lightweight recall-first collector).
- 150-query corpus in `config/justia_name_queries.txt` — broad recall-first (site:trademarks.justia.com "loan", "personal loans", "cash advance", "lending services", etc.). Minimal negatives. "Goods and Services" is optional on most queries.
- Extraction: detected_mark_name from title before first dash/" - ", URL slug fallback, serial from URL, keep raw title/snippet/query/position.
- Extremely light filtering: ONLY reject lawyers.justia.com and contracts.justia.com. **Intentionally keep** mortgage, debt, investment, bank, financial services names for later manual review.
- Scaling controls (new):
  - `--query-offset N` (default 0) — start from query index N
  - `--query-limit N` — process only N queries after offset
  - `--shuffle-queries` — randomize query order (fixed seed for test reproducibility)
  - `--append` — append to existing output with deduplication by normalized_name/serial/URL
  - `--max-results-per-query 20-100` for higher recall
- Output always includes `manual_decision` and `notes` columns (left blank for human review).
- Always writes `data/apify/justia_name_candidates.meta.json` with full run metadata (timestamps, query_offset/limit/shuffle, counts, absolute paths).
- **MANDATORY post-write verification** (new): After writing JSONL+CSV, verify both files exist, JSONL line count == final_candidates_written, CSV line count == final_candidates_written + 1 (header), CSV has all stable columns. If any check fails, exit(1) with clear error. **Never print "SUCCESS - Wrote X candidates" if files are missing or 0 bytes.**

**Critical lesson from this session (repeated across 10+ runs)**:
Multiple discovery scripts (both the full verification version and the name-only collector) printed "SUCCESS", "Wrote X candidates", "files_written", and detailed counts while the actual files on disk were missing, 0 bytes, or the data/apify directory did not exist. This happened even after directory creation commands. The root causes were missing explicit `mkdir -Force data\apify`, silent exceptions before the write block, and reporting based on in-memory counts instead of post-write filesystem checks.

**Durable rule**: For all discovery/collector scripts in this project, ALWAYS:
1. Explicitly ensure output directory exists (`New-Item -ItemType Directory -Force data\apify`)
2. Perform post-write verification (file existence, exact line counts, header present)
3. Use `dir data\apify`, Get-ChildItem, or Python line count before claiming success in any OUTPUT block or summary.
4. If verification fails, report the actual filesystem state and recommend fix (do not fabricate counts).

See `references/justia-name-collector-scaling.md` (added this session) for batch scaling checklist, metadata spec, verification script pattern, and full list of query patterns that produced high recall without heavy negatives.

**Mandatory Response Format (justia-coder profile — non-negotiable, repeated user correction)**:
ALL responses in this profile/project must be a ```python code block containing:
- OUTPUT = {dict with task, counts, entries, summary fields}
- SUMMARY and FINAL_SUMMARY strings
- Human-readable print sections (=== TITLE ===, counts, lists)
- Exact ending line: **COPY FULL BLOCK ABOVE** (select entire code block for clean artifact)

This format is explicitly required in the user profile and triggered corrections in nearly every session. It is now the default for verification, discovery, collection, and status tasks. Violating it is no longer acceptable.

This section replaces the previous shorter Name-Only Collector description and incorporates all lessons from the full conversation (Cloudflare blockers, recall-first query tuning, persistent file-write bugs, batch scaling controls, metadata, post-write verification, and the mandatory structured output format).

**Mandatory Output Format (user preference — non-negotiable for justia-coder profile)**:
Every response must be a ```python code block containing:
- OUTPUT = {dict with task, verified_count/saved_html_count, entries list (url, word_mark, serial_number, owner, exact_visible_loan_phrase, loan_only_pass, save_status, saved_filename, notes), rejected_pages, blocked_pages, final_summary}
- SUMMARY and FINAL_SUMMARY strings that explicitly state "All data grounded in actual tool outputs", "Strict adherence to all do not rules", "No fabrication of URLs/serial/names".
- print statements for human-readable report (=== TITLE ===, counts, lists).
- Must end with exact line: **COPY FULL BLOCK ABOVE** (select entire code block for clean artifact)

This format was mandated in the user profile and every session. Violating it triggers immediate user correction. Embed in all verification, discovery, collection, and pipeline tasks.

**Updated Summary (2026-06-17)**:
- Cloudflare makes direct browser automation unreliable → Apify+USPTO fallback is now primary scaling path.
- Query tuning moved from strict "Goods and Services" + heavy negatives to recall-first broad phrases with post-SERP filtering.
- 32-query corpus + USPTO verification produced 7 candidates in smoke test.
- All candidates require manual Browser Verification Agent review + HTML save before collect_justia_trademarks.py.
- Aligns with loan_keywords.yaml expansion (title loans, cash advance, personal loans now have verified Justia backing).
- Use this section for all future Justia/loan trademark work in this profile.

(Updated from full conversation history: multiple Apify bug fixes (actor ID, schema, Run object, timeout, query recall), USPTO fallback creation, mandatory output format enforcement, and Cloudflare-driven workflow evolution.)

## Windows path separator / stale queued chunk bug

If worker logs suddenly show many `missing audio file: data\\chunks\\...` errors after a rebuild/restart, do **not** assume audio files vanished. Older/host-side queued rows may contain Windows-style paths (`data\\chunks\\station\\file.wav`) while the worker runs in a Linux container where backslashes are literal filename characters. `Path(chunk.path).is_file()` then falsely fails and the chunk gets marked `dropped`.

**Robust fix:** In `worker/consumer.py`, do not only replace separators inline. Add a resolver that tries the current path, a separator-normalized path, and the container chunk mount for legacy `data/chunks/...` rows:

```python
def _resolve_audio_path(self, raw_path: str) -> Path:
    normalized = raw_path.replace("\\\\", "/")
    candidates = [Path(normalized)]
    if normalized.startswith("data/chunks/"):
        candidates.append(Path("/app/chunks") / normalized.removeprefix("data/chunks/"))
    elif not normalized.startswith("/"):
        candidates.append(Path("/app") / normalized)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
```

Then use `audio_path = self._resolve_audio_path(chunk.path)` in `_process_claimed()`.

**Deploy/verify checklist (do all, not just build):**

```powershell
docker compose build worker
docker compose up -d --no-deps worker
docker compose ps worker
docker exec radio-worker sh -c "grep -n '_resolve_audio_path\\|replace' /app/worker/consumer.py | head"
docker logs radio-worker --tail 40
```

A successful fix shows new `chunk transcribed` logs after restart. `fpcalc` errors remain non-fatal. Do **not** repair/reset `dropped` rows in production DB without explicit operator confirmation, because DB mutation is outside read-only ops.

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
