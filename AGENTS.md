# Agent Memory — Radio Ad-Sensing Pipeline

**Read this first in every session.** Single source for "where we are" so nothing gets lost between chats.

## Memory OS (mandatory workflow)

**Before coding** — load project memory (Obsidian vault in-repo):

```txt
project-memory/00_Project_Overview.md
project-memory/01_Current_Architecture.md
project-memory/02_Operating_Policy.md
project-memory/03_Forbidden_Assumptions.md
project-memory/04_Agent_Load_Order.md
```

Optional MCP: `config/obsidian-mcp.json` → obsidian-mcp-server searches `project-memory/`.

**After coding** — verify (no production DB writes in harness):

```bash
python tools/harness/run_all.py
```

Optional self-heal (explicit restart only): `python tools/harness/run_all.py --execute-self-heal`

**Completion report** must include: files changed, tests run, harness result (`tools/harness/reports/latest.md`), remaining risks, memory files updated.

### Required memory updates

If work changes **behavior**, **policy**, **station state**, **classifier logic**, or **architecture**, a corresponding project-memory file **must** be created or updated before the task is complete:

| Change type | Action |
|---|---|
| Behavioral / policy | `python tools/memory/decision_logger.py "title" --context "…" --decision "…" --related-files <paths>` |
| Operational failure | `python tools/memory/incident_logger.py "title" --symptoms "…"` |
| Station lifecycle | `python tools/memory/station_logger.py CALLSIGN keep\|watch\|pause\|rotate_out --reasoning "…"` |
| Architecture / ops policy | Edit `01_Current_Architecture.md` or `02_Operating_Policy.md` |
| Session status | Update `project-memory/Latest_Status.md` |

Undocumented classifier, station-policy, or dashboard-routing changes **fail** `decision_harness`. Work is incomplete until harness passes.

**AI layer:** Hermes local + Ollama on-box — do not assume Gemini / Claude API / OpenAI unless explicitly configured.

## Current state (2026-06-10)

| Item | Status |
|---|---|
| **Opus review gate** | ✅ **CLOSED** — ทุก WP ship (`plan/opus-review-plan-6165b3.md`) |
| **Tests** | **112/112** passing (`pytest`) |
| **Grafana metrics** | ✅ WP-10c — `plan/wp10c-grafana-metrics-report.md` (stage/ASR/LLM/dedup/ingest/alerter + Ollama scrape) |
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
| WP-10c Grafana expansion | `plan/wp10c-grafana-metrics-report.md` |
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
- **Monitoring:** Prometheus + Grafana (19 panels, `$station` filter) — scrape 9101–9104 + ollama:11434 + dcgm:9400
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

## Hermes Telegram (remote ops)

- Context: `.hermes.md` (auto-loaded by Hermes gateway when cwd is this repo)
- Skill: `/pipeline-ops` → `.agents/skills/pipeline-ops/SKILL.md`
- Live status: `.\scripts\pipeline-status.ps1` (query DB via `docker exec radio-worker`)
- **Do not** read `data/pipeline.db` from Windows host during Docker ingest (stale bind-mount)

## Every session (required)

Agent runs automatically — **do not ask user to type commands**. Full runbook: `.cursor/rules/agent-commands.mdc`

| เมื่อ | Agent ทำ |
|---|---|
| เริ่ม session | `AGENTS.md` + **project-memory/** (5 mandatory files) + `understand-chat` สำหรับ architecture |
| ก่อนปิดงาน | `.venv\Scripts\pytest` + `python tools/harness/run_all.py` + migrate `data/test.db` |
| หลัง commit โครงสร้างใหญ่ | `/understand` |
| pipeline ops | `.\scripts\pipeline-loan-ops.ps1` + docker exec queries |

Optional: `/caveman`, `headroom proxy`

Bootstrap: `final-install-list.md` · `docs/agent-tooling.md`

## Session checklist for agent

- [ ] Read this file + **project-memory/** (5 mandatory files) + relevant `plan/handoff-*.md`
- [ ] Run `pytest` before claiming done
- [ ] Run `python tools/harness/run_all.py` before claiming done
- [ ] Update `plan/` report or handoff when closing a phase
- [ ] Update `project-memory/` when architecture or ops policy changes
