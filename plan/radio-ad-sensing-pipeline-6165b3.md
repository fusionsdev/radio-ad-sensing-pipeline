# Autonomous Radio Ad-Sensing Pipeline

A fully local Docker Compose pipeline on Ubuntu (12GB NVIDIA GPU) that ingests 4–10 U.S. News/Talk radio streams 24/7, chunks and transcribes them with faster-whisper, extracts loan/funding ad details with a local Qwen2.5-7B via Ollama, dedups fuzzily (boosted by chromaprint audio fingerprinting), stores everything in SQLite, sends first-seen alerts via the Telegram Bot API, and exposes a read-only FastAPI dashboard plus Prometheus/Grafana monitoring.

## Agreed Decisions (from grilling session)

| Branch | Decision |
|---|---|
| Scale | 4–10 concurrent stations, single GPU box |
| Segmentation | Fixed 60–120s chunks with 5–10s overlap; transcribe everything |
| ASR | faster-whisper `medium.en`, int8_float16 (~1.5GB VRAM, ~10x RT) |
| LLM | Ollama + Qwen2.5-7B-Instruct Q4_K_M (~5GB VRAM), JSON-schema structured output |
| Schema | LLM extracts: is_ad, ad_category, company_name, phone_number, website, offer_summary, key_claims, confidence — `station`/`timestamp` are injected from chunk metadata, never asked of the LLM |
| Dedup | Fuzzy (rapidfuzz >85% on transcript + normalized company/phone/category); alert first sighting per ad per N days; store every airing linked to canonical ad; same ad + same station within 3min counts as **one** airing (overlap de-double-count) |
| Storage | SQLite (WAL); raw chunks kept 24–48h; detected-ad audio archived permanently; transcripts forever |
| Deployment | Docker Compose: ingestor, worker (GPU), alerter, ollama; NVIDIA container toolkit; restart:always + healthchecks |
| Ingestion resilience | `stations.yaml` config; ffmpeg reconnect + supervisor loop w/ backoff; gap logging; ops alert if station down >15min |
| Telegram | Outbound-only Bot API (sendMessage + audio clip); no inbound webhook |
| Backlog | Bounded queue (~2h); drop-oldest with gap log + ops alert |
| Observability | Structured JSON logs, status table in SQLite, daily Telegram digest + Prometheus metrics & Grafana dashboards |
| Audio pre-filter | Chromaprint fingerprinting as **annotation only** — tags repeats of known produced spots to skip redundant LLM calls and strengthen dedup; everything still transcribed (zero recall loss) |
| Web dashboard | FastAPI + Jinja2/HTMX, read-only, LAN-only: detections feed w/ audio playback, canonical ads w/ airing frequency, station health, gap timeline |

## Architecture

```
stations.yaml ──> [ingestor]  ffmpeg per station ──> chunks/ (WAV/Opus on disk)
                                                        │ (SQLite-backed work queue)
                  [worker]    fingerprint ─> faster-whisper ─> Ollama extract ─> fuzzy dedup ─> detections
                                                        │
                  [alerter]   reads unalerted detections ──> Telegram Bot API (first-seen + ops + daily digest)
                  [janitor]   (in worker) retention cleanup, gap detection, status rollup
                  [dashboard] FastAPI + HTMX (read-only, SQLite) ──> LAN browser
                  [prometheus]<── /metrics from ingestor, worker, alerter, dashboard
                  [grafana]   dashboards: queue depth, GPU util (dcgm/nvidia-smi exporter),
                              detections/hr, station uptime, ASR/LLM latency
```

- **Queue**: a `chunks` table in SQLite (status: pending/processing/done/dropped). File-system chunks referenced by path. No Redis/Celery.
- **SQLite concurrency**: 3 writer processes (ingestor, worker, alerter) on one DB — WAL mode + `busy_timeout=5000` + retry-on-`SQLITE_BUSY` wrapper in `shared/db.py`; keep transactions short; dashboard opens read-only connections.
- **VRAM budget**: ~1.5GB Whisper + ~5GB LLM + overhead ≈ 8GB, safe on 12GB. Fingerprinting (chromaprint) is CPU-only.
- **Fingerprint flow** (in worker, before ASR): compute chromaprint feature vector of chunk → **offset-tolerant match** against stored fingerprints of archived ad clips (sliding-window correlation over chromaprint vectors — a whole-chunk hash will never match a 30s ad at a random offset inside a 90s chunk) → on hit, record airing immediately and mark chunk `known_ad`; transcription still runs, but the LLM extraction step is skipped for `known_ad` chunks. If sliding-window chromaprint proves too weak, fall back to landmark hashing (audfprint-style) in a later iteration.
- **Ad clip boundaries**: when a new ad is detected, map the LLM-flagged ad text back to Whisper **segment timestamps** to cut the ad clip from the chunk for archiving/fingerprinting (±2s padding).
- **Metrics**: each Python service exposes `/metrics` via `prometheus-client`; GPU metrics via `nvidia-dcgm-exporter` (or `nvidia-smi`-based exporter); Grafana provisioned with datasource + dashboards as code.

## Repository Layout

```
radio-ad-sensing-pipeline/
├── docker-compose.yml
├── .env.example              # TELEGRAM_BOT_TOKEN, CHAT_ID, etc.
├── config/
│   ├── stations.yaml         # name, url, format, enabled
│   └── settings.yaml         # chunk_len, overlap, retention, dedup window, thresholds
├── ingestor/                 # ffmpeg supervisor per station, chunk writer, gap logger
├── worker/                   # queue consumer: fingerprint -> transcribe -> extract -> persist
│   ├── fingerprint.py        # chromaprint (pyacoustid/fpcalc) compute + match vs known ads
│   ├── transcribe.py         # faster-whisper wrapper
│   ├── extract.py            # Ollama client, JSON-schema prompt, validation (pydantic)
│   └── dedup.py              # rapidfuzz matching against canonical ads
├── alerter/                  # Telegram sender: ad alerts, ops alerts, daily digest
├── dashboard/                # FastAPI + Jinja2/HTMX read-only UI
│   ├── main.py               # routes: /, /ads, /ads/{id}, /stations, /gaps, /audio/{id}
│   └── templates/
├── monitoring/
│   ├── prometheus.yml        # scrape configs
│   └── grafana/              # provisioned datasource + dashboard JSON
├── shared/                   # db.py (schema + migrations), models.py, queue.py, logging, metrics.py
├── data/                     # SQLite db, chunks/, ad_archive/   (volume)
└── tests/
```

## Database Schema (core tables)

- `stations` — id, name, url, enabled
- `chunks` — id, station_id, path, start_ts, end_ts, status, error
- `transcripts` — chunk_id, text, asr_duration_ms
- `canonical_ads` — id, company_name, phone_norm, category, first_seen, last_seen, airing_count, archived_audio_path
- `detections` — id, chunk_id, canonical_ad_id (nullable until matched), full JSON fields, confidence, alerted(bool)
- `gaps` — station_id, start_ts, end_ts, reason (stream down / dropped backlog)
- `fingerprints` — canonical_ad_id, chromaprint_vector (blob), duration; `chunks` gains `known_ad_id` (nullable)
- `status` — rolling counters for digest/health

## Implementation Phases

1. **Scaffold + DB** — repo layout, SQLite schema/migrations, settings/stations config loading, structured logging.
2. **Ingestor** — ffmpeg subprocess per station (reconnect flags), 90s chunks w/ 7s overlap, enqueue rows, gap logging, supervisor backoff.
3. **Worker: ASR** — faster-whisper medium.en int8; bounded-queue consumer; drop-oldest policy.
4. **Worker: extraction** — Ollama structured-output call with core-field schema; pydantic validation; retry-once on invalid JSON; phone-number normalization (spelled-out → digits).
5. **Dedup + persistence** — rapidfuzz match vs canonical_ads within N-day window; create/attach detections; 3-min same-station airing window to avoid overlap double-count; cut ad clip via Whisper segment timestamps and archive it.
6. **Alerter** — first-seen Telegram alert (formatted message + audio file), ops alerts (station down >15min, queue drops), daily digest.
7. **Dockerization** — Compose with NVIDIA runtime for worker, official Ollama image w/ model pull, healthchecks, restart policies, volumes.
8. **Fingerprint annotation** — chromaprint vector per chunk; offset-tolerant sliding-window match vs `fingerprints` of canonical ad clips; auto-fingerprint newly archived ad audio; skip LLM on `known_ad` chunks; airing counter fast-path.
9. **Web dashboard** — FastAPI + Jinja2/HTMX service: detections feed with audio playback (serves from `ad_archive/`), canonical-ad table with airing frequency, station health page, gap timeline. Read-only, bound to LAN interface.
10. **Prometheus + Grafana** — `prometheus-client` metrics in all services (queue depth, chunks processed, ASR/LLM latency histograms, detections, station uptime, drops); dcgm-exporter for GPU; Prometheus + Grafana containers with provisioned dashboards and basic alert rules (queue saturation, station down).
11. **Tests + hardening** — unit tests for dedup/normalization/schema validation/fingerprint matching; fixture transcripts (real loan-ad copy) as an extraction eval set; end-to-end smoke test with a recorded stream sample.

## Key Risks / Mitigations

- **Whisper mangles phone numbers** — normalize spelled-out numbers; dedup doesn't rely on exact phone match.
- **LLM false positives** (show segments about loans vs actual ads) — prompt includes ad-signal cues (call to action, phone/URL, "sponsored"); confidence field; threshold before alerting.
- **Ads split across chunk boundaries** — 5–10s overlap + dedup absorbs duplicates from overlap.
- **Stream URL rot** — gap logging + >15min down ops alert surfaces it fast; URLs are operator-maintained in `stations.yaml`.
- **GPU contention** — single worker process serializes Whisper batches; Ollama keep_alive pins the LLM; both fit in 12GB.
- **ASR throughput has zero headroom at 10 stations** — 10 stations × real-time + ~8% overlap exceeds the ~10x RT budget of medium.en. Mitigations, in order: batched inference (BatchedInferencePipeline), drop overlap to 5s, fall back to `small.en` above 8 stations. Validate measured RTF in Phase 3 before committing to station count.
- **SQLite write contention** — WAL + busy_timeout + retry wrapper (see Architecture); if contention still bites, funnel all writes through the worker process.
- **Fingerprint false matches** (similar jingles/spot variants) — conservative match threshold; transcription always runs, so a false `known_ad` tag only skips extraction for that airing, never loses audio/transcript.
- **Dashboard exposure** — read-only, no auth, so bind to LAN/localhost only; Grafana gets its own login.

## Dev Tooling Setup (from `final-install-list.md`)

Agent/dev tooling that accompanies this project — 14 skills kept + 2 repos installed now, 4 deferred.

### Installed now

| Repo | Type | Install |
|---|---|---|
| `JuliusBrussee/caveman` | Skill pack (output token saver; replaces old caveman; adds `/caveman`, `/caveman-commit`, `/caveman-review`, `/caveman-stats`, `/caveman-compress`) | `irm https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.ps1 \| iex` |
| `chopratejas/headroom` | MCP server (input token compressor) | `pip install "headroom-ai[mcp]"` + `headroom mcp install` |

### Deferred installs

| Repo | When |
|---|---|
| `Egonex-AI/Understand-Anything` | After Phase 1 scaffold exists (needs code to graph) |
| `oraios/serena` | When codebase grows (semantic code retrieval) |
| `upstash/context7` | Anytime, for latest library docs |
| `doobidoo/mcp-memory-service` | Maybe unnecessary if headroom's cross-agent memory suffices |

### Skills kept (14, from `mattpocock/skills`)

- **engineering**: `diagnose`, `grill-with-docs`, `improve-codebase-architecture`, `prototype`, `review`, `setup-matt-pocock-skills`, `tdd`, `to-issues`, `to-prd`, `triage`, `zoom-out`
- **productivity**: `grill-me`, `handoff`, `write-a-skill`
- **misc**: `setup-pre-commit`

14 skills removed (writing/personal/deprecated ones) from `.agents/skills/`, `.qoder/skills/`, and `skills-lock.json` — full list in `final-install-list.md`.

## Out of Scope (deferred)

- PostgreSQL, multi-box scaling
- Inbound Telegram bot commands
- Dashboard write/ops controls (enable/disable stations, mute ads) — possible phase 2
- Hard audio pre-filtering (skipping transcription) — fingerprinting is annotation-only by design
