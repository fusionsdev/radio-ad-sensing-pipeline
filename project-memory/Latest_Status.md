# Latest Status

**Updated:** 2026-06-23

## Pipeline

- All work packages shipped; Opus review gate closed
- Enabled stations: `kfi-am-640`, `wbap-am-820` per `config/stations.yaml`
- Docker full stack on Win GPU host — `radio-dashboard` on `127.0.0.1:8081`

## Memory OS

- Phase 1: Obsidian vault + harness + MCP hooks — shipped
- Phase 1.5: decision/incident/station loggers + memory harness — shipped
- Phase 1.75: Memory API + **radiosense-aistudio** `/memory` tab — shipped
- Phase 1.8: Memory metrics, timeline, incident/decision analytics — shipped
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