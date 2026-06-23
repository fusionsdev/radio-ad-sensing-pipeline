# RADIOSENSE_MEMORY_OS_PHASE_1_75_MEMORY_DASHBOARD.md

## Objective

Build a Memory Dashboard for RadioSense Memory OS.

Current status:

* Memory OS Phase 1 complete
* Memory OS Phase 1.5 complete
* Project Memory exists
* Harness exists
* Decision Logger exists
* Incident Logger exists
* Station Logger exists
* Memory Harness exists

The next goal is to make Memory OS visible inside the active RadioSense Dashboard.

---

# CRITICAL REPOSITORY LAYOUT

There are TWO separate codebases.

## Pipeline Repository

Contains:

```txt
H:\DEV\projects\radio-ad-sensing-pipeline
```

Responsibilities:

```txt
Backend API
Memory files
Harness
Project Memory
Hermes
Pipeline services
```

**Legacy in-repo dashboard:** `dashboard/` folder — FastAPI + Jinja. **Do not add Memory UI here.**

---

## Active Dashboard Repository (frontend only)

**Correct path:**

```txt
H:\DEV\github_sandbox\radiosense-aistudio
```

**NOT** `H:\DEV\github_sandbox\radiosense` (older/alternate React app — do not use for new UI work).

URLs:

```txt
Dev:     http://localhost:5150/     (npm run dev — vite --port=5150)
Preview: http://localhost:4150/     (npm run preview — vite preview port 4150)
```

Backend API proxy target (both dev + preview):

```txt
http://127.0.0.1:8081
```

All UI work must happen in **radiosense-aistudio**.

---

# IMPORTANT RULE

DO NOT build the Memory UI inside:

* `radio-ad-sensing-pipeline/dashboard/` (legacy backend-embedded UI)
* `github_sandbox/radiosense/` (non-active dashboard)

Before modifying frontend code, inspect **radiosense-aistudio**:

```txt
package.json
vite.config.ts
src/App.tsx
src/lib/routes.ts
src/lib/api.ts
src/components/Sidebar.tsx
src/components/*View.tsx
```

Determine actual route/tab structure first.

---

# Discovery (verified 2026-06-23)

## Frontend routes (radiosense-aistudio)

Tab-based navigation — **not** React Router file-per-route. Canonical map in `src/lib/routes.ts`:

| Path | Tab ID |
|------|--------|
| `/` | `command-center` |
| `/actions` | `action-center` |
| `/harvest` | `harvest-control` |
| `/health` | `pipeline-health` |
| `/stations` | `live-stations` |
| `/detections` | `live-detections` |
| `/keywords` | `keyword-intelligence` |
| `/advertisers` | `advertisers` |
| `/reports` | `reports` |
| `/metrics` | `metrics-interpreter` |
| `/system-control` | `system-control` |
| `/settings` | `settings` |
| `/support` | `support` |

**Memory page target:** add `/memory` → `memory` tab.

## API configuration

* `src/lib/api.ts` — `BASE_URL = import.meta.env.VITE_RADIO_API_BASE_URL ?? ""`
* Blank `VITE_RADIO_API_BASE_URL` → relative `/api/*` proxied to `127.0.0.1:8081`
* `vite.config.ts` — `server.port: 5150`, `preview.port: 4150`

## Dashboard structure

* Entry: `src/main.tsx` → `src/App.tsx`
* Views: `src/components/*View.tsx` (not `src/pages/`)
* Sidebar nav: `src/components/Sidebar.tsx` (`navItems` array)
* Shared ops context: `src/context/OpsProvider.tsx`
* Polling pattern: direct `fetch` in `api.ts` + 30s interval in App (no TanStack Query)

---

# Architecture

```txt
project-memory/
       │
       ▼
radio-ad-sensing-pipeline  (read-only Memory API)
       │
       ▼
github_sandbox/radiosense-aistudio  (Memory tab UI)
       │
       ▼
http://localhost:5150/memory
```

---

# Scope

Build **Memory Dashboard** displaying:

* Memory Health
* Harness Status
* Recent Decisions
* Recent Incidents
* Station Lifecycle Changes
* Latest Status Freshness

---

# Code Boundaries

## Allowed Changes

**Pipeline repo** (`radio-ad-sensing-pipeline`):

```txt
dashboard/routes/memory.py   (or equivalent router)
Memory API layer
Harness integration (dashboard_harness probes)
Read-only file parsing
tests/test_memory_api.py
```

**Dashboard repo** (`radiosense-aistudio`):

```txt
src/lib/routes.ts
src/lib/api.ts
src/components/MemoryView.tsx
src/components/Sidebar.tsx
src/App.tsx
```

## Forbidden Changes

Do NOT modify:

```txt
Classifier logic
Loan detection logic
Station rotation logic
Production DB schema
Production DB contents
Hermes runtime behavior
Ingestor runtime behavior
radiosense-aistudio UI outside Memory feature (unless nav wiring)
```

This phase is visibility-only.

---

# Backend API

Implement in **radio-ad-sensing-pipeline**. Wire router in `dashboard/main.py`.

```txt
GET /api/memory/health
GET /api/memory/status
GET /api/memory/harness/latest
GET /api/memory/decisions?limit=10
GET /api/memory/incidents?limit=10
GET /api/memory/stations?limit=20
```

Reuse existing parsers where possible:

* `tools/memory/memory_report.py` → health
* `tools/harness/reports/latest.json` → harness

Read only from:

```txt
project-memory/
tools/harness/reports/latest.json
tools/harness/reports/latest.md
```

No writes. No DB mutations. No service restarts.

---

# Endpoint Requirements

## GET /api/memory/health

```json
{
  "status": "PASS",
  "core_files": "PASS",
  "runbooks": "PASS",
  "stations": "PASS",
  "decisions": "PASS",
  "freshness": "PASS",
  "links": "PASS"
}
```

## GET /api/memory/status

Combined snapshot: health subchecks + `Latest_Status.md` age + vault markdown count.

## GET /api/memory/harness/latest

Latest harness report. Prefer `latest.json`, fallback `latest.md`.

## GET /api/memory/decisions?limit=10

```json
[{ "date": "", "title": "", "summary": "", "path": "" }]
```

## GET /api/memory/incidents?limit=10

```json
[{ "date": "", "title": "", "symptoms": "", "path": "" }]
```

## GET /api/memory/stations?limit=20

```json
[{ "station": "", "status": "", "last_change": "", "path": "" }]
```

---

# Frontend Implementation

Repository: `H:\DEV\github_sandbox\radiosense-aistudio`

1. Add `src/components/MemoryView.tsx`
2. Add `/memory` in `src/lib/routes.ts`
3. Add sidebar item **Memory** in `src/components/Sidebar.tsx`
4. Wire tab in `src/App.tsx` (`currentTab === 'memory'`)
5. Add API helpers + types in `src/lib/api.ts`

### UI sections

* **Memory Health** — subcheck badges (PASS/WARNING/FAIL)
* **Harness Status** — status, overnight readiness, timestamp
* **Recent Decisions** — date, title, summary table
* **Recent Incidents** — date, title, symptoms table
* **Station Changes** — station, status, last change table

### Resilience

Degraded empty states when:

* `project-memory` missing
* decision/incident folders empty
* `latest.json` missing
* API unreachable

Do not crash the app.

---

# Harness Updates

In **pipeline repo**, extend `tools/harness/runners/dashboard_harness.py`:

Verify 200 OK on:

```txt
/api/memory/health
/api/memory/status
/api/memory/harness/latest
```

---

# Tests

**Backend** (pipeline repo):

```bash
pytest tests/test_memory_api.py
pytest tests/test_harness.py
```

**Frontend** (radiosense-aistudio):

```bash
npm run typecheck
npm run build
```

No test runner configured in aistudio; manual check at `http://localhost:5150/memory`.

---

# Acceptance Criteria

Phase 1.75 complete when:

* [x] Memory tab exists in **radiosense-aistudio** at `/memory`
* [x] Memory API endpoints exist in pipeline repo
* [x] Memory Health visible in UI
* [x] Harness status visible
* [x] Recent decisions visible
* [x] Recent incidents visible
* [x] Station lifecycle history visible
* [x] `dashboard_harness` validates memory endpoints
* [x] No production DB writes
* [x] No classifier / station rotation / ingestor changes

## Shipped 2026-06-23

**Docker follow-up:** `radio-dashboard` required image rebuild — old container returned 404 on `/api/memory/*`. Fixed via `dashboard/Dockerfile` + compose volume mounts. Documented in `project-memory/Runbooks/Memory Dashboard.md` and `project-memory/Incidents/2026-06-23-memory-api-404-docker.md`.

---

# Required Completion Report

Return:

## Discovery

* frontend routes discovered (`src/lib/routes.ts`)
* API base URL (`VITE_RADIO_API_BASE_URL` + proxy)
* dashboard structure (`*View.tsx` + tab nav)

## Files Changed

List every file in **both repos**.

## Tests Run

List results.

## Harness Result

PASS / FAIL

## Core Code Touched

```txt
Backend API files touched: (pipeline repo paths)
Frontend files touched: (radiosense-aistudio paths only)
```

## Remaining Risks

List deferred items.

## Recommendation

Should Phase 2 (zvec Semantic Memory) begin now?

---

# Future Phase 2 (do not implement)

* zvec semantic indexing
* automatic note embeddings
* memory search API
* incident similarity search
* decision recommendation engine