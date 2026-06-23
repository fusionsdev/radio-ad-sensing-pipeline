# Incident

Date: 2026-06-23

## Symptoms

- `http://localhost:5150/memory` showed **Degraded — API unreachable**
- Browser error: `API /api/memory/health failed: 404 Not Found`
- `http://127.0.0.1:8081/health` returned 200 (backend up)
- `curl http://127.0.0.1:8081/api/memory/health` → 404

## Root Cause

Container `radio-dashboard` was running a **pre–Phase 1.75 image**:

1. `dashboard/routes/memory.py` not present in container
2. `/app/tools/` missing — Memory API imports `tools.memory.vault_reader`
3. `dashboard/Dockerfile` originally copied only `dashboard/`, not `tools/` or `project-memory/`

Code existed on the Windows host; Docker image was never rebuilt after Memory API landed.

## Resolution

1. Updated `dashboard/Dockerfile` — `COPY tools/` and `COPY project-memory/`
2. Updated `docker-compose.yml` — read-only bind mounts for live vault/tools
3. Rebuilt and recreated dashboard:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml build dashboard
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d dashboard
```

4. Verified: `/api/memory/health` → 200, `"status":"PASS"`

## Prevention

- After any Memory API or `dashboard/routes/*` change affecting Docker: **rebuild `radio-dashboard`**
- Documented in [[Runbooks/Memory Dashboard]]
- `dashboard_harness` probes memory endpoints — run `python tools/harness/run_all.py` before claiming deploy done

## Related Components

- `radio-dashboard` (Docker, port 8081 on Windows dev)
- `radiosense-aistudio` frontend (`:5150/memory`)
- `dashboard/routes/memory.py`
- `tools/memory/vault_reader.py`