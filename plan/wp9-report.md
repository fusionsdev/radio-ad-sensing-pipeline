# WP-9 Completion Report — Read-only Web Dashboard

**Handoff reference:** `.windsurf/plans/handoff-wp9-dashboard-6165b3.md`  
**Completed:** 2026-06-10  
**Status:** Complete — all mandatory scope and acceptance criteria met

---

## Summary

FastAPI + Jinja2/HTMX read-only dashboard over SQLite. All DB access uses `get_connection(read_only=True)`. Missing database shows a friendly page instead of crashing. Empty and seeded databases both render correctly.

---

## Deliverables

| Item | Path |
|---|---|
| FastAPI app | `dashboard/main.py` |
| Read-only queries | `dashboard/queries.py` |
| CLI entry | `dashboard/__main__.py` (`python -m dashboard`) |
| Templates | `dashboard/templates/` (base, index, ads, ad_detail, stations, gaps, no_database, HTMX partial) |
| Seed fixture | `tests/fixtures/seed_dashboard.py` |
| Dashboard tests | `tests/test_dashboard.py` (13 tests) |
| Settings | `dashboard_host`, `dashboard_port`, `db_path` in `config/settings.yaml` |
| Optional deps | `pyproject.toml` → `[project.optional-dependencies.dashboard]` |

### Routes

| Route | Description |
|---|---|
| `GET /` | Overview: today's chunks/detections, ads total, queue depth, station health |
| `GET /ads` | Canonical ads table, sort by `last_seen`, HTMX pagination |
| `GET /ads/{id}` | Ad detail, detections, transcript excerpts, audio player |
| `GET /stations` | Per-station health: enabled, last chunk, chunks/gaps 24h |
| `GET /gaps` | Gap timeline, last 48h |
| `GET /audio/{id}` | Serve archived audio; path locked to `data/ad_archive/` |
| `GET /health` | JSON: `db_reachable`, `pending_count` |

---

## Test results

```
37 passed in 1.21s
```

| Suite | Count |
|---|---|
| Original Phase 1 tests | 18 |
| WP-9 dashboard tests | 13 |
| Worker tests (pre-existing) | 6 |

### Acceptance criteria

| Criterion | Result |
|---|---|
| `pytest` green (old + new) | ✅ 37/37 |
| `python -m dashboard` serves pages | ✅ uvicorn on `127.0.0.1:8080` |
| Zero writable DB connections from dashboard | ✅ `test_dashboard_never_opens_writable_connection` |
| Every route 200 on empty + seeded DB | ✅ |
| `/audio` traversal rejected | ✅ 404 |
| Missing DB → friendly page | ✅ |

---

## Run

```bash
pip install -e ".[dashboard]"
python -c "from shared.db import migrate; migrate('data/pipeline.db')"
python -m tests.fixtures.seed_dashboard  # optional: use seed_dashboard_db() in Python
python -m dashboard
# → http://127.0.0.1:8080
```

Seed for dev:

```python
from pathlib import Path
from tests.fixtures.seed_dashboard import seed_dashboard_db
seed_dashboard_db(Path("data/pipeline.db"))
```

---

## Deviations from handoff / PLAN.md

| Item | Notes |
|---|---|
| Audio path in seed | Stores absolute path under `data/ad_archive/`; tests monkeypatch `AD_ARCHIVE_DIR` for isolation |
| `GET /audio/{id}` | Accepts canonical ad id or detection id (detection resolved via join) |
| Auth / metrics / Docker | Out of scope per handoff — not implemented |

---

## Out of scope (unchanged)

- Auth, write/ops controls
- Prometheus `/metrics` (WP-10b)
- Docker (WP-7)
- Websockets / live updates

---

## Next

Per original roadmap: pipeline phases 2–6 populate live data. Dashboard is ready to display ingestor/worker/alerter output as it arrives.
