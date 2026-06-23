# Dashboard feature conventions — radio-ad-sensing-pipeline

How the FastAPI dashboard (`dashboard/`) is structured and the conventions to
follow when adding a new page, control button, or JSON API to it. Captured
after adding the Radio Harvest control panel (2026-06-19). Read this before
adding any dashboard surface.

## App structure

- Entry: `dashboard/main.py` → `create_app(db_path=None) -> FastAPI` (factory).
  `dashboard/__main__.py` runs it via uvicorn.
- Routes can be flat in `main.py` OR grouped via a **router factory** in
  `dashboard/routes/<name>.py`. Prefer the router-factory pattern for any
  multi-endpoint feature (see `dashboard/routes/novelty.py` and
  `dashboard/routes/harvest.py` as references).
- Templates: Jinja2 in `dashboard/templates/`, extend `base.html`. Subfolders
  are fine (`templates/harvest/*.html`). Nav links live in `base.html`'s `<nav>`.
- DB: the app resolves `resolved_db` once and passes it into routers. **All
  GET routes must use `get_connection(db_path, read_only=True)`** — there is a
  strict test that enforces this (see Tests below).

## Router-factory pattern (copy this shape)

```python
# dashboard/routes/<name>.py
def create_<name>_router(db_path: Path, *, format_ts, no_database_handler) -> APIRouter:
    router = APIRouter()
    # define helpers, then @router.get / @router.post ...
    return router
```

Wire it into `main.py` next to the novelty include:

```python
from dashboard.routes.harvest import create_harvest_router
app.include_router(create_harvest_router(resolved_db, format_ts=_format_ts, no_database_handler=_no_database))
```

Always pass the shared `format_ts` (epoch-float → "YYYY-MM-DD HH:MM UTC") and
the `_no_database` handler in. Add your own format helpers inside the factory.

## POST action buttons — watchdog 303-redirect precedent

Operator buttons POST to `/<feature>/<action>` and redirect (303) back to the
control page with a `?msg=<flash_key>` query param. This matches the ONLY
existing POST in the repo (`/ops/watchdog/restart/{station_id}`). Example:

```python
@router.post("/radio-harvest/probe")
def action_probe() -> RedirectResponse:
    result = harvest_api.run_control_action("probe")
    msg = "probe_ok" if result.get("ok") else "probe_fail"
    return RedirectResponse(url=f"/radio-harvest?msg={msg}", status_code=303)
```

Buttons are plain `<form method="post">` with a `btn-review` class (already
styled in `base.html`). Disable buttons server-side via a context flag (e.g.
`running`) and render `disabled` + `title="..."` on the `<button>`. Use
`onsubmit="return confirm('...')"` for destructive/stop actions.

## Safe subprocess wrapper — fixed allowlist + single seam

When a button must run a CLI, **never** interpolate request input into argv.
Use a fixed command allowlist of constant argv tuples and a single
monkeypatchable seam so tests don't shell out:

```python
ALLOWED_COMMANDS = {
    "probe": (sys.executable, "scripts/harvest_control.py", "probe", "--limit", "20"),
    ...
}

def _run_subprocess(argv):  # tests monkeypatch THIS
    completed = subprocess.run(list(argv), cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
    return {"ok": completed.returncode == 0, "returncode": ..., "stdout": ..., "stderr": ...}

def run_control_action(action):
    if action not in ALLOWED_COMMANDS: raise UnknownActionError(action)
    return _run_subprocess(ALLOWED_COMMANDS[action])
```

Arbitrary action names must be unrouted (404/405), never dispatched. See
`dashboard/harvest_api.py`.

## PITFALL — status file uses ISO strings, DB uses epoch floats

The runtime status file (`runtime/harvest_status.json`) stores timestamps as
**ISO-8601 strings** (`"2026-06-19T02:48:20Z"`), but the dashboard's shared
`format_ts` expects **epoch floats** (from `chunks.start_ts`). Rendering a
status-file timestamp with `format_ts` raises
`TypeError: 'str' object cannot be interpreted as an integer`.

Fix: add a dual formatter inside the router factory that handles both:

```python
def _fmt_when(value):
    if value is None or value == "": return "—"
    if isinstance(value, (int, float)): return format_ts(value)   # epoch
    from datetime import datetime
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).strftime("%Y-%m-%d %H:%M UTC")
```

Use `format_ts` for chunk/DB timestamps, `fmt_when` for status-file fields
(`started_at`, `stopped_at`, `last_updated`, `export.at`).

## Read-only guarantee (enforced by test)

`test_dashboard.py::test_dashboard_never_opens_writable_connection` patches
`shared.db.get_connection` to raise if called with `read_only=False`. Any new
GET route that touches the DB must use `read_only=True` or this test fires.
When adding a new GET-heavy feature, add a parallel strict test (see
`test_harvest_dashboard.py::test_harvest_get_routes_never_open_writable`) that
patches BOTH `shared.db.get_connection` and your module's local
`get_connection` binding.

## Tests

- Dedicated file per feature: `tests/test_harvest_dashboard.py`.
- Add new GET routes to the `HTML_ROUTES` list in `tests/test_dashboard.py`
  so the `200 on empty db` / `200 on seeded db` sweep covers them.
- Reuse the seed fixture `tests/fixtures/seed_dashboard.py` (seeds a station,
  chunk, ad, detection, keyword_hit).
- For subprocess-wrapping endpoints, monkeypatch the module's `_run_subprocess`
  seam — do NOT shell out in tests.
- **Run tests with the project venv**, not the system python:
  `.venv\Scripts\python.exe -m pytest ...` (system python lacks
  `prometheus_client`, which `shared.metrics` imports at `dashboard.main`
  import time — collection fails with ModuleNotFoundError otherwise).

## Rebuilding the dashboard container (deploy surface, distinct from local)

**The dashboard you hit at `http://127.0.0.1:8081` is the Docker container
`radio-dashboard`, NOT your local source.** The image bakes the source in via
`COPY` (no live mount of `dashboard/`), so a container that has been `Up` for
days serves code from build-time. This is the single most common confusion
when a freshly-added route returns `{"detail":"Not Found"}`.

### Symptom → cause → fix

| Symptom | Cause | Fix |
|---|---|---|
| `GET /new-route` → `{"detail":"Not Found"}` but the route IS in `dashboard/routes/*.py` and wired in `main.py` | Running container predates the code change (image is stale) | Rebuild the image (below) |
| Container `Restarting (1)` / `unhealthy` after a rebuild | A router committed since the last build imports a package not `COPY`-ed into the Dockerfile, or uses a FastAPI feature needing a dep not in `pyproject` `[dashboard]` extras | Read `docker logs radio-dashboard --tail 40`, find the boot traceback, fix the Dockerfile/extras |

### PITFALL — a rebuild can surface LATENT build-time bugs

This is the dangerous one. A dashboard that has run happily for days can
**crash-loop after rebuild** if, in the meantime, a router was committed that
imports source not present in the image or uses a FastAPI feature needing an
extra dependency. The latent bug was invisible while the old image kept
running. Two real instances (both hit on 2026-06-19 when rebuilding for the
harvest panel):

1. `dashboard/routes/novelty.py` imports `alerter.novelty_reporter` and
   `worker.novelty_review`, but `dashboard/Dockerfile` only `COPY`-ied
   `shared/` and `dashboard/`. → boot crash
   `ModuleNotFoundError: No module named 'alerter'`.
   **Fix:** the Dockerfile must also `COPY alerter/ ./alerter/` and
   `COPY worker/ ./worker/`. Both modules are import-light (sqlite3/yaml/
   shared only, no GPU/ML deps), so this is safe for the dashboard image.

2. `novelty.py` defines POST routes with FastAPI `Form(...)` params. FastAPI
   requires `python-multipart` for any `Form`/`File` param, lazily raising
   `RuntimeError: Form data requires "python-multipart"` at route-decoration
   time (boot) — NOT at request time. The dep was missing from
   `[project.optional-dependencies] dashboard`.
   **Fix:** add `"python-multipart>=0.0.6"` to the `dashboard` extras in
   `pyproject.toml`.

3. The harvest action buttons (`POST /radio-harvest/{probe,start,stop}`) shell
   out to `scripts/harvest_control.py` via the allowlist. But
   `dashboard/Dockerfile` did not `COPY scripts/` into the image — the buttons
   booted fine (the allowlist is just argv tuples) but every POST failed at
   runtime with `ModuleNotFoundError: No module named 'scripts'` (status looked
   OK because `subprocess.run` swallowed it into the result dict). This is
   invisible until someone clicks a button.
   **Fix:** `COPY scripts/ ./scripts/`. Lesson: any source tree referenced by
   `sys.executable` argv in the allowlist must be COPY'd, not just trees that
   are `import`-ed at boot.

Lesson: when a rebuild crashes the dashboard OR a button silently fails, scan
`dashboard/routes/*.py` AND `dashboard/harvest_api.py` (the allowlist) for
(1) `from <pkg>` imports and (2) `Form(`/`File(` params and (3) argv tuples
naming source files — then confirm each is satisfied by a `COPY` directive +
an extras entry. Boot-time import/Form failures crash the whole app; runtime
argv failures crash only the button and hide in the result dict.

### Distinguish local-source from the container

Before touching the Dockerfile, confirm the bug is container-only by booting
current source locally against the real DB:

```bash
# local source (proves the code is correct even if the container is broken)
DASHBOARD_PORT=8082 DASHBOARD_HOST=127.0.0.1 .venv/Scripts/python.exe -m dashboard
# then GET 127.0.0.1:8082/<route>  → 200 means code is fine, container is stale
```

Use a free port (the container owns 8081). If local works but the container
doesn't, it's a build/Dockerfile issue, not a route issue.

### Rebuild command (Windows-dev stack, dashboard only)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d --build dashboard
```

This rebuilds just the dashboard image and recreates the container; other
services (ingestor/worker/alerter) keep running. Then **wait for health** —
`docker ps` shows `Up (healthy)` only after ~10-30s; the `HEALTHCHECK` polls
`/health`. A fresh `Restarting (1)` status in the first ~15s is normal only
if it then flips to `Up (healthy)`; persistent `Restarting (N)` means boot is
crashing → read the logs.

### Verify the rebuilt container actually serves the route

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8081/health          # 200
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8081/radio-harvest   # 200
curl -s http://127.0.0.1:8081/api/harvest/status | python -m json.tool
```

If `/health` is 200 but `/radio-harvest` is still 404, the rebuild used a
stale cache layer — force it with `docker compose build --no-cache dashboard`.

## Live verification recipe (real DB, no shell-out needed for GETs)

Boot uvicorn serving the factory against the real DB and curl the new routes
to confirm they render with real data (not just empty 200s):

```bash
.venv/Scripts/python.exe -m uvicorn dashboard.main:create_app --factory --host 127.0.0.1 --port 8090 --log-level warning &
curl -s localhost:8090/<route> | head   # check status, byte size, key strings present
curl -s localhost:8090/api/<feature>/<endpoint> | python -m json.tool
```

Kill the server after. This catches timestamp-rendering bugs and template
errors that TestClient sometimes masks.

## Where things live (after the Radio Harvest panel)

| Concern | Path |
|---|---|
| Harvest control API layer | `dashboard/harvest_api.py` |
| Harvest routes (HTML + JSON) | `dashboard/routes/harvest.py` |
| Harvest templates | `dashboard/templates/harvest/{index,status,detections,queue,stations}.html` |
| Control panel route | `/radio-harvest` |
| JSON endpoints | `/api/harvest/{probe,stop,start,status,detections,queue-health,stations}` |
| Status file (read by API) | `runtime/harvest_status.json` |
