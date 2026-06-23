# WP Memory Dashboard Phase 1.75 — Completion Report

**Date:** 2026-06-23  
**Status:** SHIPPED

## Discovery

### Frontend routes (active dashboard)

**Repo:** `H:\DEV\github_sandbox\radiosense-aistudio` (not generic `github_sandbox/`, not `radiosense/`)

Tab-based navigation via `src/lib/routes.ts`:

| Path | Tab ID |
|------|--------|
| `/memory` | `memory` (new) |
| `/` | `command-center` |
| `/actions` | `action-center` |
| … | (see `routes.ts`) |

Views live in `src/components/*View.tsx` — no `src/pages/` router files.

### API base URL

- `src/lib/api.ts`: `BASE_URL = import.meta.env.VITE_RADIO_API_BASE_URL ?? ""`
- Blank env → Vite proxy `/api/*` → `http://127.0.0.1:8081`
- Dev: `http://localhost:5150/` · Preview: `http://localhost:4150/`

### Dashboard structure

- Entry: `src/App.tsx` + `src/components/Sidebar.tsx`
- Memory UI: `src/components/MemoryView.tsx`
- Polling: 30s refresh in MemoryView; shared `apiFetch` pattern

## Files changed

### Pipeline repo (`radio-ad-sensing-pipeline`)

| File | Change |
|------|--------|
| `dashboard/routes/memory.py` | New read-only Memory API router |
| `dashboard/main.py` | Wire `create_memory_router()` |
| `tools/memory/vault_reader.py` | Vault + harness parsers |
| `tools/memory/_common.py` | Behavior fingerprint includes `memory.py` |
| `tools/harness/runners/dashboard_harness.py` | Probes 3 memory endpoints |
| `dashboard/Dockerfile` | COPY `tools/`, `project-memory/` |
| `docker-compose.yml` | RO bind mounts vault + tools |
| `tests/test_memory_api.py` | 6 API tests |
| `plan/radiosense-memory-os-phase-1-75.md` | Spec + acceptance |
| `project-memory/Runbooks/Memory Dashboard.md` | Ops runbook |
| `project-memory/Incidents/2026-06-23-memory-api-404-docker.md` | Deploy incident |
| `project-memory/01_Current_Architecture.md` | Two-repo + memory APIs |
| `project-memory/Latest_Status.md` | Phase 1.75 status |
| `project-memory/Decisions/2026-06-23-memory-dashboard-phase-1-75.md` | Decision record |
| `project-memory/04_Agent_Load_Order.md` | Memory dashboard load order |
| `AGENTS.md` | Active UI path + Docker rebuild note |

### Frontend repo (`radiosense-aistudio`)

| File | Change |
|------|--------|
| `src/components/MemoryView.tsx` | Memory page (all UI sections) |
| `src/lib/api.ts` | Memory types + `getMemory*` |
| `src/lib/routes.ts` | `/memory` route |
| `src/components/Sidebar.tsx` | Memory nav item |
| `src/App.tsx` | Tab + header wiring |

## Tests run

```text
pytest tests/test_memory_api.py tests/test_harness.py — 23/23 passed
python tools/harness/run_all.py — PASS, overnight readiness: ready
npm run typecheck (radiosense-aistudio) — pass
curl http://127.0.0.1:8081/api/memory/health — 200 PASS
```

No frontend test framework in aistudio.

## Harness result

**PASS** — Memory Health all subchecks pass; dashboard harness includes `/api/memory/health`, `/status`, `/harness/latest`.

## Core code touched

**Backend API:**

- `dashboard/routes/memory.py`
- `dashboard/main.py`
- `tools/memory/vault_reader.py`
- `dashboard/Dockerfile`, `docker-compose.yml`

**Frontend:**

- `radiosense-aistudio/src/components/MemoryView.tsx`
- `radiosense-aistudio/src/lib/api.ts`
- `radiosense-aistudio/src/lib/routes.ts`
- `radiosense-aistudio/src/components/Sidebar.tsx`
- `radiosense-aistudio/src/App.tsx`

**Not touched:** classifier, station rotation, ingestor, production DB schema/contents, Hermes runtime.

## Acceptance criteria

| Criterion | Met |
|-----------|-----|
| Memory page in active dashboard | ✅ `/memory` |
| Memory API endpoints | ✅ 6 routes |
| Memory Health visible | ✅ |
| Harness status visible | ✅ |
| Recent decisions visible | ✅ |
| Recent incidents visible | ✅ (empty state when none) |
| Station lifecycle visible | ✅ |
| Dashboard harness validates memory | ✅ |
| No prod DB writes | ✅ read-only |
| No classifier/rotation/ingestor changes | ✅ |

## Post-ship fix

Docker `radio-dashboard` returned 404 until image rebuild (missing `memory.py` + `/app/tools`). Documented in `project-memory/Runbooks/Memory Dashboard.md`.

## Remaining risks

- Memory API deploy requires `docker compose … build dashboard` after backend changes
- No automated frontend tests in aistudio
- Harness reports inside container follow host `tools/harness/reports/` via bind mount
- Phase 2 zvec semantic search not implemented

## Recommendation

**Defer Phase 2** until operators use `/memory` for ~1 week. Validate that read-only visibility covers ops needs before investing in embeddings and semantic retrieval.