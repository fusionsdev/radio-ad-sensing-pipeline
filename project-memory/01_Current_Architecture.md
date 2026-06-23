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

## Dashboard JSON APIs (harness probes)

| Endpoint | Purpose |
|---|---|
| `/api/health` | DB reachability + queue snapshot |
| `/api/stations?limit=100` | Station rows + ingest health |
| `/api/detections?limit=50` | Recent detections |
| `/api/harvest/status` | Harvest session + DB snapshot |

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