# Latest Status

**Updated:** 2026-06-23

## Pipeline

- All work packages shipped; Opus review gate closed
- Conservative harvest enabled stations: `klif-am-570`, `wbap-am-820` per `config/stations.yaml`
- Patch E implemented/tested locally: watchdog fixed-harvest mode blocks auto-promotion, preserves pool safety locks on sync, and records `manual_attention` instead of disabling fixed-harvest stations at recovery limits
- Patch E controlled watchdog audit stopped at T+15: no promote/disable drift, but watchdog still queued `restart_station` for stale `klif-am-570`
- Patch E.1 watchdog-only audit passed T+30: no `promote_station`, no `disable_station`, no `restart_station`, no station drift, pool locks remained `0`; watchdog is running healthy in observe-only fixed-harvest mode
- Docker full stack on Win GPU host — `radio-dashboard` on `127.0.0.1:8081`

## Memory OS

- Phase 1: Obsidian vault + harness + MCP hooks — shipped
- Phase 1.5: decision/incident/station loggers + memory harness — shipped
- Phase 1.75: Memory API + **radiosense-aistudio** `/memory` tab — shipped
- Phase 1.8: Memory metrics, timeline, incident/decision analytics — shipped
- Multi-agent contract: Cursor, Codex, Claude Code, Grok, Hermes shims → `AGENTS.md` — shipped
- Phase 2: zvec semantic index — deferred (`tools/memory/zvec_hooks.py` hooks only)

## Active dashboard

| Item | Value |
|---|---|
| Frontend repo | `H:\DEV\github_sandbox\radiosense-aistudio` |
| Memory page | `http://localhost:5150/memory` |
| Backend | `http://127.0.0.1:8081` (Docker `radio-dashboard`) |

**Deploy note:** Memory API changes require `docker compose … build dashboard` — old images return 404 on `/api/memory/*`. Fixed 2026-06-23 — see [[Incidents/2026-06-23-memory-api-404-docker]].

## Harness

Last run target: `python tools/harness/run_all.py` — classifier, dashboard (incl. memory probes), self_healing, station, hermes, decision, memory.

## Related

- [[00_Project_Overview]]
- [[Runbooks/Memory Dashboard]]
- [[Decisions/2026-06-23-memory-dashboard-phase-1-75]]
- [[Decisions/Memory OS Phase 1.5]]
