# Current Architecture

## Pipeline flow

```txt
stations.yaml → ingestor (ffmpeg) → chunks/ + SQLite queue
                                        ↓
              worker: fingerprint → ASR → LLM extract → dedup → detections
                                        ↓
              alerter (Telegram) ← unalerted detections
              dashboard (FastAPI, read-only) ← SQLite
              watchdog (health, promotion, recovery)
              prometheus/grafana ← /metrics (9101–9104)
```

## Services (docker-compose)

| Service | Role | Metrics |
|---|---|---|
| ingestor | ffmpeg per station, chunk writer | 9101 |
| worker | ASR + LLM + dedup (GPU) | 9102 |
| alerter | Telegram outbound | 9103 |
| dashboard | FastAPI + HTMX + JSON APIs | 9104 |
| ollama | Qwen2.5-7B local LLM | 11434 |
| watchdog | station health, pool promotion | — |

## Queue model

- Table: `chunks` (pending / processing / done / dropped)
- No Redis/Celery
- SQLite WAL + `busy_timeout=5000` + `@retry_on_busy` in `shared/db.py`

## Classifier layers

1. **Production gating** — `shared/consumer_personal_loan.py` + taxonomy YAML
2. **Ops classifier** — `scripts/loan_classifier.py` (station rotation, Hermes `/pipeline-ops`)
3. **LLM extraction** — Ollama JSON schema; `station`/`timestamp` injected from chunk metadata

## Dashboard — two codebases

| Layer | Location | Notes |
|---|---|---|
| **Backend API** | `radio-ad-sensing-pipeline` → Docker `radio-dashboard` `:8081` | FastAPI, SQLite read-only |
| **Active UI** | `H:\DEV\github_sandbox\radiosense-aistudio` | React, `:5150` dev / `:4150` preview |
| **Legacy UI** | `pipeline/dashboard/` templates | Do not add new operator UI here |
| **Legacy React** | `github_sandbox/radiosense` | Superseded by aistudio |

```txt
radiosense-aistudio (:5150) ──proxy /api──► radio-dashboard (:8081) ──read──► SQLite + project-memory/
```

## Dashboard JSON APIs (harness probes)

| Endpoint | Purpose |
|---|---|
| `/api/health` | DB reachability + queue snapshot |
| `/api/stations?limit=100` | Station rows + ingest health |
| `/api/detections?limit=50` | Recent detections |
| `/api/harvest/status` | Harvest session + DB snapshot |
| `/api/memory/health` | Memory OS vault health (Phase 1.75) |
| `/api/memory/status` | Health + Latest_Status freshness |
| `/api/memory/harness/latest` | Latest harness report JSON/MD |
| `/api/memory/decisions` | Recent decision notes |
| `/api/memory/incidents` | Recent incident notes |
| `/api/memory/stations` | Station lifecycle memory files |

Memory API requires `tools/` + `project-memory/` in dashboard image — see [[Runbooks/Memory Dashboard]].

## Memory OS (this vault)

```txt
project-memory/ (Obsidian vault, git-synced)
      ↓
obsidian-mcp-server (agent read/search)
      ↓
Hermes / Cursor agents (load before coding)
      ↓
tools/harness/run_all.py (verify after coding)
```

Phase 2 hook (not implemented): `tools/memory/zvec_hooks.py` — markdown → zvec semantic index.

## Related notes

- [[00_Project_Overview]]
- [[02_Operating_Policy]]
- [[Runbooks/Pipeline Status]]