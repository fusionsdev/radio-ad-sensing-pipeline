# Phase 1 Completion Report — Scaffold + DB

**Project:** Autonomous Radio Ad-Sensing Pipeline  
**Phase:** 1 — Scaffold + DB  
**Handoff reference:** `plan/handoff-phase1-scaffold-db-6165b3.md`  
**Completed:** 2026-06-10  
**Status:** Complete — all mandatory scope and acceptance criteria met

---

## Summary

Phase 1 delivers the repository scaffold, SQLite schema with migrations, Pydantic models, YAML/environment config loading, and structured JSON logging. The `shared/` package is import-light (no GPU/ML dependencies) and ready for ingestor, worker, and alerter services in later phases.

---

## Deliverables

### 1. Repository scaffold

Per the "Repository Layout" section of `PLAN.md`:

| Path | Contents |
|---|---|
| `ingestor/` | Stub `__init__.py` only |
| `worker/` | Stub `__init__.py` only |
| `alerter/` | Stub `__init__.py` only |
| `dashboard/` | Stub `__init__.py` only |
| `monitoring/` | Stub `__init__.py` only |
| `shared/` | Core Phase 1 modules (see below) |
| `tests/` | Pytest suite (18 tests) |
| `config/` | `stations.yaml`, `settings.yaml` |
| `data/` | Gitignored runtime directory (SQLite DB, future chunks) |

No business logic in service packages. No Phase 2+ code. No Docker files.

### 2. `shared/db.py`

- Connection factory with **WAL mode** and **`busy_timeout=5000`**
- **`retry_on_busy`** decorator for `SQLITE_BUSY` / locked errors (exponential backoff)
- **Read-only** connection variant (`?mode=ro`) for future dashboard use
- Sequential migration runner over numbered SQL files in `shared/migrations/`
- `schema_migrations` table tracks applied versions
- Short **`transaction()`** context manager for commit/rollback

**Migration:** `shared/migrations/001_initial.sql`

**Tables created (8 core):**

| Table | Notes |
|---|---|
| `stations` | id, name, url, format, enabled |
| `chunks` | incl. nullable `known_ad_id`, `error` column |
| `transcripts` | chunk_id (unique), text, asr_duration_ms |
| `canonical_ads` | company, phone_norm, category, airing metadata |
| `detections` | full extraction fields + `alerted` flag |
| `gaps` | station_id, start/end ts, reason |
| `fingerprints` | `chromaprint_vector` as **BLOB**, duration |
| `status` | key/value rolling counters |

**Indexes:** `chunks.status`, `chunks.station_id`, `detections.canonical_ad_id`

### 3. `shared/models.py`

Pydantic models mirroring all core tables plus:

- **`AdExtraction`** — LLM schema: `is_ad`, `ad_category`, `company_name`, `phone_number`, `website`, `offer_summary`, `key_claims`, `confidence`
- **`AdExtractionWithMetadata`** — adds `station` and `timestamp` (metadata only, not in LLM schema)
- **`ChunkStatus`** enum: pending / processing / done / dropped
- Helper: `detection_from_extraction()`

### 4. Config loading

| File | Purpose |
|---|---|
| `config/stations.yaml` | Station list: name, url, format, enabled |
| `config/settings.yaml` | chunk_len=90, overlap=7, retention, dedup window, thresholds |
| `shared/config.py` | `load_stations()`, `load_settings()`, `load_telegram_settings()` |
| `.env.example` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` placeholders |

### 5. `shared/logging.py`

Structured JSON logging via stdlib `logging` + custom `JsonFormatter`. Every log line includes a **`service`** field (service name).

### 6. Project plumbing

| File | Purpose |
|---|---|
| `pyproject.toml` | Python ≥3.11; deps: pydantic, pydantic-settings, PyYAML; dev: pytest |
| `README.md` | Setup, migrate, and pytest instructions |
| `.gitignore` | `data/`, `.env`, `__pycache__/`, venv caches |
| `.env.example` | Telegram placeholders (no secrets committed) |

Git repository was already initialized before Phase 1 work began.

### 7. Tests

| File | Coverage |
|---|---|
| `tests/test_db.py` | Migrations, idempotency, WAL/busy_timeout, read-only conn, retry wrapper, concurrent writes |
| `tests/test_config.py` | YAML parsing, Telegram env settings |
| `tests/test_models.py` | LLM schema validation, metadata separation, detection helper |
| `tests/test_logging.py` | JSON output with service name |

---

## Test results

```
platform win32 -- Python 3.11.15, pytest-9.0.3
18 passed in 0.26s
```

### Acceptance criteria verification

| Criterion | Result |
|---|---|
| `pytest` passes | ✅ 18/18 |
| `migrate('data/test.db')` creates all 8 tables | ✅ Verified |
| Concurrent writes without unhandled `SQLITE_BUSY` | ✅ `test_concurrent_writes_do_not_raise_unhandled_busy` |
| No Phase 2+ code, no Docker | ✅ Confirmed |

**Migrate smoke test:**

```bash
python -c "from shared.db import migrate; migrate('data/test.db')"
```

Creates: `canonical_ads`, `chunks`, `detections`, `fingerprints`, `gaps`, `stations`, `status`, `transcripts` (+ internal `schema_migrations`).

---

## Deviations from `PLAN.md` / handoff

| Item | Handoff / PLAN expectation | Actual implementation | Impact |
|---|---|---|---|
| Config parsing | "parsed into pydantic-settings objects" | YAML → `pydantic.BaseModel` (`PipelineSettings`, `StationsFile`); `.env` → `pydantic-settings` (`TelegramSettings`) | None — YAML is file-based, not env-based; pattern is idiomatic |
| `dashboard/templates/` | Listed in PLAN layout | Not created in Phase 1 | None — handoff scope requires stub packages only; templates belong to Phase 9 |
| `shared/queue.py` | Listed in PLAN layout | Not created | None — not in Phase 1 handoff scope; likely Phase 2 |
| `shared/metrics.py` | Listed in PLAN layout | Not created | None — Prometheus metrics are Phase 10 |
| `stations.format` | In `stations.yaml` config | Added to `stations` table schema | Positive — aligns config with DB, no PLAN conflict |
| `schema_migrations` table | Not listed in core schema | Added for migration runner | Implementation detail; does not affect domain tables |
| Pre-commit hooks | Optional (`setup-pre-commit` skill) | Not configured | Deferred — can add before Phase 2 if desired |
| Standards+spec review | Optional (`review` skill) | Not run | Deferred — no blocking issues found in self-check |

No architectural decisions from `PLAN.md` were re-litigated. No GPU/ML dependencies added to `shared/`.

---

## Constraints satisfied

- **`fingerprints.chromaprint_vector`** stored as BLOB (feature vector, not hash)
- **`shared/` import-light** — only pydantic, PyYAML, stdlib sqlite3/logging
- **Retry wrapper** is the primary concurrency mitigation for 3 future writer processes
- **Transactions kept short** via `transaction()` context manager

---

## Files added or modified (Phase 1)

```
.gitignore
.env.example
README.md
pyproject.toml
config/stations.yaml
config/settings.yaml
ingestor/__init__.py
worker/__init__.py
alerter/__init__.py
dashboard/__init__.py
monitoring/__init__.py
shared/__init__.py
shared/db.py
shared/models.py
shared/config.py
shared/logging.py
shared/migrations/001_initial.sql
tests/__init__.py
tests/test_db.py
tests/test_config.py
tests/test_models.py
tests/test_logging.py
plan/phase1-report.md          ← this report
```

---

## Next phase

**Phase 2 — Ingestor** (not started):

- ffmpeg subprocess per enabled station (reconnect flags)
- 90s chunks with 7s overlap → `data/chunks/`
- Enqueue rows in `chunks` table (`status=pending`)
- Gap logging to `gaps` table
- Supervisor loop with exponential backoff

See `PLAN.md` § Implementation Phases, item 2.
