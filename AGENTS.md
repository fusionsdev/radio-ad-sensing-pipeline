# Agent Memory — Radio Ad-Sensing Pipeline

**Read this first in every session.** Single source for "where we are" so nothing gets lost between chats.

## Current state (2026-06-10)

| Item | Status |
|---|---|
| **Opus review gate** | ✅ **CLOSED** — ทุก WP ship (`plan/opus-review-plan-6165b3.md`) |
| **Tests** | **103/104** passing (`pytest`; 1 pre-existing `.env` Telegram leak) |
| **Ingest resilience** | ✅ WP ship — `plan/wp-ingest-resilience-report.md` (Hermes Sonnet + Opus gate) |
| **DB migrate** | `python -c "from shared.db import migrate; migrate('data/pipeline.db')"` |
| **Docker** | ✅ full stack up on Win GPU host — `plan/wp7b-docker-smoke-20260610.md` |
| **Operator smoke** | ✅ CA+TX ingestor+worker+alerter — `plan/ca-tx-ingestor-smoke-20260610.md` |
| **Handoff** | `plan/handoff-ca-tx-smoke-20260610.md` |
| **Stations enabled** | `kfi-am-640`, `wbap-am-820` in `config/stations.yaml` |
| **Git** | initial commit + ingest-resilience on `main` |

## Work packages (all shipped)

| WP | Report |
|---|---|
| Phase 1 Scaffold+DB | `plan/phase1-report.md` |
| WP-2 Ingestor | `plan/wp2-report.md` |
| WP-3 ASR worker | `plan/wp3-report.md` |
| WP-4 LLM extraction | `plan/wp4-report.md` |
| WP-5 Dedup | `plan/wp5-report.md` |
| WP-6 Alerter | `plan/wp6-report.md` |
| WP-7a Docker skeleton | `plan/wp7a-report.md` |
| WP-7b Docker finalize | `plan/wp7b-report.md` |
| WP-8 Fingerprint | `plan/wp8-report.md` |
| WP-9 Dashboard | `plan/wp9-report.md` |
| WP-10a Monitoring config | `plan/wp10a-report.md` |
| WP-10b Instrument metrics | `plan/wp10b-report.md` |
| WP-11a Tests+hardening | `plan/wp11a-report.md` |
| WP-11b Extraction eval | `plan/wp11b-report.md` |
| WP-12 RAM disk + janitor | `plan/wp12-report.md` |
| WP-13 Production hardening | `plan/wp13-hardening-report.md` |
| WP-ingest-resilience | `plan/wp-ingest-resilience-report.md` |

## Canonical docs (read before coding)

1. `PLAN.md` — architecture, schema, all 11 phases, risks — **do not re-litigate**
2. `plan/opus-review-plan-6165b3.md` — review gate (closed)
3. `plan/work-dispatch-6165b3.md` — batch routing history
4. `final-install-list.md` — skills + plugins installed

## Key technical facts (don't forget)

- **Stack:** Python 3.11+, SQLite WAL, faster-whisper + Ollama/Qwen, Telegram outbound, FastAPI dashboard (`python -m dashboard`)
- **docker-compose.yml** 10 services — metrics ports 9101–9104; worker waits on `ollama-pull`
- **`shared/`** must stay import-light — no GPU/ML deps
- **SQLite concurrency:** `shared/db.py` → WAL + `busy_timeout=5000` + `@retry_on_busy`
- **`fingerprints.chromaprint_vector`** = BLOB feature vector, not hash
- **LLM schema** excludes `station`/`timestamp` — metadata injected separately
- **Queue:** `chunks` table (pending/processing/done/dropped), no Redis
- **Chunk storage:** transient WAVs via `chunks_dir` / `CHUNKS_DIR`; Docker uses tmpfs `/app/chunks` (ingestor+worker); janitor deletes after processing + periodic sweep

## Optional operator smoke (not CI)

- WP-2 F6: ✅ CA+TX pipeline smoke — `plan/ca-tx-ingestor-smoke-20260610.md` (ingestor + worker + alerter dry-run)
- WP-7b: ✅ Win RTX 3090 — `docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d`; dashboard **:8081**

## Understand-Anything (codebase graph)

Installed globally; graph output lives in **this repo** under `.understand-anything/`.

| When | Command |
|---|---|
| **One-time auto-update setup** | `.\scripts\setup-understand-auto.ps1` then restart Cursor |
| First time / after big refactor | `/understand` or `/understand --full` |
| Explore graph UI | `/understand-dashboard` or `.\scripts\understand-dashboard.ps1` |
| Check graph on disk | `.\scripts\understand-graph-status.ps1` |
| Architecture Q&A | `/understand-chat How does chunk processing work?` |
| Before commit | `/understand-diff` |
| Onboarding doc | `/understand-onboard` |

**Auto-run:** with setup done, agent refreshes graph on session start (stale commit) and after `git commit` via `.cursor/hooks.json` — no manual `/understand` each time.

Full command list: `README.md` § Codebase map. Plugin paths: `final-install-list.md`.

## Session checklist for agent

- [ ] Read this file + relevant `plan/handoff-*.md` if starting new work
- [ ] Run `pytest` before claiming done
- [ ] Update `plan/` report or handoff when closing a phase
