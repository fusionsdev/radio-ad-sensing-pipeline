# RadioSense — Project Overview

**Vertical:** Consumer personal loans only  
**Stack:** Local-first Python pipeline on Docker (Win GPU host)  
**AI ops:** Hermes local gateway — not cloud LLM APIs by default

## Mission

Ingest U.S. News/Talk radio streams 24/7, transcribe with faster-whisper, extract ad metadata with local Ollama/Qwen, deduplicate airings, alert on first-seen loan ads via Telegram, and expose a read-only FastAPI dashboard with Prometheus/Grafana monitoring.

## Detection scope (loan-only)

| Valid | Invalid |
|---|---|
| BillsHappen, personal loan, cash advance, installment loan | Tax relief, insurance, car financing, window financing, supplements, identity protection |

Canonical taxonomy: `config/consumer_personal_loan_taxonomy.yaml`  
Excluded verticals: `config/excluded_verticals.yaml`

## Current operators

| Item | Value |
|---|---|
| Batch enabled stations | 10 (see `.hermes.md`) |
| Classifier | `scripts/loan_classifier.py` (strict phrase-level) |
| DB reads (live) | `docker exec radio-worker` only — never host bind-mount during ingest |
| Tests | `pytest` (112+ cases) |
| Harness | `python tools/harness/run_all.py` |

## Repo anchors

- Architecture spec: `PLAN.md`
- Session memory: `AGENTS.md`
- Hermes context: `.hermes.md`
- Stations: `config/stations.yaml`
- Project memory load order: [[04_Agent_Load_Order]]

## Related notes

- [[01_Current_Architecture]]
- [[02_Operating_Policy]]
- [[03_Forbidden_Assumptions]]
- [[Glossary]]