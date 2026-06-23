# Handoff: WP-9 — Read-only Web Dashboard (Phase 9)

Self-contained brief for Composer 2.5 to implement the FastAPI + Jinja2/HTMX read-only dashboard over the existing SQLite database.

## Context (read first)

- `PLAN.md` (repo root) — §Web dashboard decision row, §Architecture, §Implementation Phases item 9.
- `plan/phase1-report.md` — Phase 1 is DONE. **Reuse** `shared/db.py` (`get_connection(read_only=True)`), `shared/models.py`, `shared/config.py`, `shared/logging.py`. Do not reimplement.
- Run `pytest` first: 18/18 must pass.

## Scope — WP-9 ONLY

Implement in `dashboard/` (no GPU/ML deps):

1. **`dashboard/main.py`** — FastAPI app, all DB access via **read-only connections** only:
   - `GET /` — overview: counts (chunks today, detections today, ads total), per-station last-chunk age (health), queue depth (pending count).
   - `GET /ads` — canonical ads table: company, category, phone, first/last seen, airing_count; sort by last_seen; simple HTMX pagination.
   - `GET /ads/{id}` — detail: all detections for that ad, transcript excerpts, `<audio>` player for archived clip.
   - `GET /stations` — per-station: enabled, last chunk ts, chunks/24h, gap count/24h.
   - `GET /gaps` — recent gaps timeline (table grouped by station, last 48h).
   - `GET /audio/{detection_or_ad_id}` — serve archived ad audio file (`FileResponse`); **must resolve paths strictly inside `data/ad_archive/` (reject traversal)**.
   - `GET /health` — JSON: db reachable, pending count.
2. **Templates** — `dashboard/templates/` Jinja2 + htmx via CDN; one `base.html`; minimal clean CSS (single static file or inline). No Node/build step.
3. **Empty-state friendly** — DB currently has no detections/ads (pipeline phases 2–6 not built); every page must render sensibly with zero rows. Provide `tests/fixtures/seed_dashboard.py` (or a pytest fixture) that seeds fake stations/chunks/ads/detections for dev + tests.
4. **Run** — `python -m dashboard` → uvicorn on `127.0.0.1:8080` (host/port via settings; default LAN-safe). Add `fastapi`, `uvicorn`, `jinja2` to a `dashboard` optional-dependency group in `pyproject.toml`.
5. **Read-only discipline** — dashboard never opens a writable connection. If `data/pipeline.db` doesn't exist, show a clear "no database yet" page instead of crashing (read-only open fails on missing file — handle it).

## Tests

- httpx `TestClient`: every route 200 on seeded DB **and** on empty DB.
- `/audio` path-traversal attempt → 404/400.
- Assert no write: monkeypatch `get_connection` to fail if `read_only=False` is requested from dashboard code.
- Existing 18 tests still pass.

## Acceptance criteria

- `pytest` green (old + new).
- `python -m dashboard` serves all pages against a seeded dev DB.
- Zero writable DB connections from dashboard code.

## Out of scope

- Auth, write/ops controls, Prometheus metrics endpoint (WP-10b), Docker (WP-7), websockets/live updates.

## Report back

Write `plan/wp9-report.md`: deliverables, test results, screenshots optional, deviations.
