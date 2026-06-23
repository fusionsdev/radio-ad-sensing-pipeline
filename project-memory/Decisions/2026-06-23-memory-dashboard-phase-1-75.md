# Decision

Date: 2026-06-23

## Context

Memory OS Phase 1.5 added vault loggers and harness validation, but operators had no in-dashboard visibility. The active frontend lives in `github_sandbox/radiosense-aistudio`, separate from the pipeline repo.

## Decision

Phase 1.75 adds read-only Memory API routes in the pipeline backend and a Memory tab in radiosense-aistudio:

- `GET /api/memory/health`, `/status`, `/harness/latest`, `/decisions`, `/incidents`, `/stations`
- `dashboard/routes/memory.py` wired in `dashboard/main.py`
- Frontend Memory page at `/memory` in `radiosense-aistudio`

No writes to project-memory from the API. Visibility-only.

## Impact

Operators can see memory health, harness status, recent decisions/incidents, and station lifecycle notes from the active dashboard without opening Obsidian.

## Rollback

Remove `create_memory_router()` from `dashboard/main.py` and delete `dashboard/routes/memory.py`. Remove Memory tab from radiosense-aistudio.

## Docker packaging (post-ship fix)

Initial deploy hit 404: `radio-dashboard` image lacked `memory.py` and `/app/tools/`.

Added to image and compose:

- `dashboard/Dockerfile` — `COPY tools/`, `COPY project-memory/`
- `docker-compose.yml` — bind mounts `./project-memory:ro`, `./tools:ro`

Rebuild command documented in [[Runbooks/Memory Dashboard]].

## Related Files

- `dashboard/routes/memory.py`
- `dashboard/main.py`
- `dashboard/Dockerfile`
- `docker-compose.yml`
- `tools/memory/vault_reader.py`
- `tools/harness/runners/dashboard_harness.py`
- `H:\DEV\github_sandbox\radiosense-aistudio\src\components\MemoryView.tsx`
- `H:\DEV\github_sandbox\radiosense-aistudio\src\lib\api.ts`
- `H:\DEV\github_sandbox\radiosense-aistudio\src\lib\routes.ts`

## Related

- [[Runbooks/Memory Dashboard]]
- [[Incidents/2026-06-23-memory-api-404-docker]]
- [[01_Current_Architecture]]