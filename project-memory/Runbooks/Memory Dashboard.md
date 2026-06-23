# Memory Dashboard Runbook

## Two repositories (do not mix)

| Repo | Path | Role |
|---|---|---|
| **Pipeline** | `H:\DEV\projects\radio-ad-sensing-pipeline` | Backend API, `project-memory/`, harness, Docker stack |
| **Active frontend** | `H:\DEV\github_sandbox\radiosense-aistudio` | React dashboard UI only |

**Do not** build Memory UI in:

- `radio-ad-sensing-pipeline/dashboard/` (legacy FastAPI + Jinja)
- `github_sandbox/radiosense/` (older React app)

## URLs

| Surface | URL |
|---|---|
| Frontend dev | `http://localhost:5150/memory` |
| Frontend preview | `http://localhost:4150/memory` |
| Backend API (Docker Win) | `http://127.0.0.1:8081` |
| API proxy | Vite proxies `/api/*` → `127.0.0.1:8081` when `VITE_RADIO_API_BASE_URL` is blank |

## Memory API (read-only)

All routes return JSON; no writes to vault or DB.

```txt
GET /api/memory/health
GET /api/memory/status
GET /api/memory/harness/latest
GET /api/memory/decisions?limit=10
GET /api/memory/incidents?limit=10
GET /api/memory/stations?limit=20
GET /api/memory/metrics
GET /api/memory/timeline?limit=50
GET /api/memory/incidents/analytics
GET /api/memory/decisions/categories
```

Implementation:

- Router: `dashboard/routes/memory.py`
- Parsers: `tools/memory/vault_reader.py`
- Data: `project-memory/`, `tools/harness/reports/latest.json`

## Frontend wiring (radiosense-aistudio)

| File | Change |
|---|---|
| `src/lib/routes.ts` | `/memory` → tab `memory` |
| `src/components/Sidebar.tsx` | nav item **Memory** |
| `src/App.tsx` | render `MemoryView` |
| `src/components/MemoryView.tsx` | UI sections |
| `src/lib/api.ts` | `getMemory*` helpers |

Start frontend:

```powershell
cd H:\DEV\github_sandbox\radiosense-aistudio
npm run dev
```

## Docker dashboard (required for :8081)

Memory API ships in the **pipeline** backend. Container `radio-dashboard` must include:

- `dashboard/routes/memory.py` (in image)
- `/app/tools/` (for `tools.memory.vault_reader`)
- `/app/project-memory/` (vault read)

### Rebuild after Memory API changes

```powershell
cd H:\DEV\projects\radio-ad-sensing-pipeline
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml build dashboard
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d dashboard
```

### Verify

```powershell
curl http://127.0.0.1:8081/api/memory/health
curl http://127.0.0.1:8081/api/memory/status
```

Expected: HTTP 200, `"status":"PASS"` (or WARNING/FAIL with valid JSON — not 404).

## Troubleshooting

### Symptom: Memory page shows "Degraded — API unreachable" / 404

**Cause:** `radio-dashboard` running an **old image** built before Phase 1.75. Old image lacked `memory.py` and `/app/tools`.

**Fix:** Rebuild + recreate dashboard (commands above).

**Confirm inside container:**

```powershell
docker exec radio-dashboard ls /app/dashboard/routes/memory.py
docker exec radio-dashboard ls /app/tools/memory/vault_reader.py
```

### Symptom: `/health` works but `/api/memory/*` 404

Same root cause — partial old routing. Rebuild dashboard image.

### Symptom: PASS in curl but stale vault data

Bind mounts (read-only) live-update vault without rebuild:

```yaml
# docker-compose.yml dashboard service
- ./project-memory:/app/project-memory:ro
- ./tools:/app/tools:ro
```

Harness report updates require host `python tools/harness/run_all.py` (or copy `latest.json` into mounted `tools/harness/reports/`).

## Harness

`tools/harness/runners/dashboard_harness.py` probes:

```txt
/api/memory/health
/api/memory/status
/api/memory/harness/latest
```

Run full suite:

```bash
python tools/harness/run_all.py
```

## Related

- [[Decisions/2026-06-23-memory-dashboard-phase-1-75]]
- [[Incidents/2026-06-23-memory-api-404-docker]]
- [[01_Current_Architecture]]
- [[Latest_Status]]