# Handoff: Phase 1 — Scaffold + DB

A self-contained brief for a fresh agent (Cursor) to implement Phase 1 of the Autonomous Radio Ad-Sensing Pipeline: repository scaffold, SQLite schema/migrations, config loading, and structured logging.

## Context

- **Project**: fully local 24/7 radio ad-sensing pipeline (faster-whisper + Ollama/Qwen2.5-7B + SQLite + Telegram + FastAPI dashboard + Prometheus/Grafana), Docker Compose on Ubuntu with a 12GB NVIDIA GPU.
- **Full plan (read first)**: `PLAN.md` at repo root — all architecture decisions, schema, phases, and risks live there. Do not re-litigate decisions.
- **Workspace**: `h:\DEV\projects\radio-ad-sensing-pipeline` (currently contains only `PLAN.md`, `final-install-list.md`, and `.windsurf/`/`.agents/` config).
- **Language**: Python 3.11+.

## Scope — Phase 1 ONLY

Implement exactly this; do **not** start ingestor/worker/alerter/dashboard logic (Phases 2+):

1. **Repo scaffold** per the "Repository Layout" section of `PLAN.md`: create package dirs (`ingestor/`, `worker/`, `alerter/`, `dashboard/`, `monitoring/`, `shared/`, `tests/`, `config/`, `data/` gitignored) with empty/stub `__init__.py` files only — no business logic.
2. **`shared/db.py`** — SQLite connection factory + schema migrations:
   - WAL mode, `busy_timeout=5000`, retry-on-`SQLITE_BUSY` wrapper (decorator or context manager).
   - Read-only connection variant (for the future dashboard).
   - Simple sequential migration runner (numbered SQL files or in-code migrations table).
   - All tables from the "Database Schema" section of `PLAN.md`: `stations`, `chunks` (incl. `known_ad_id` nullable), `transcripts`, `canonical_ads`, `detections`, `gaps`, `fingerprints` (with `chromaprint_vector` BLOB), `status`. Add sensible indexes (`chunks.status`, `chunks.station_id`, `detections.canonical_ad_id`).
3. **`shared/models.py`** — pydantic models mirroring the tables + the LLM extraction schema (is_ad, ad_category, company_name, phone_number, website, offer_summary, key_claims, confidence — note: `station`/`timestamp` are metadata, NOT in the LLM schema).
4. **Config loading** — `config/stations.yaml` (name, url, format, enabled) and `config/settings.yaml` (chunk_len=90, overlap=7, retention hours, dedup window days, thresholds) parsed into pydantic-settings objects; `.env.example` with `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` placeholders (never commit real values).
5. **`shared/logging.py`** — structured JSON logging setup (stdlib `logging` + JSON formatter or `structlog`), service-name field.
6. **Project plumbing** — `pyproject.toml` (deps for Phase 1 only: pydantic, pydantic-settings, PyYAML, pytest), `README.md` stub, `.gitignore` (`data/`, `.env`, `__pycache__`), git init if not already.
7. **Tests** — pytest: migrations apply cleanly to a tmp DB; retry wrapper retries on locked DB; config files parse; models validate. Target: all green via `pytest`.

## Acceptance criteria

- `pytest` passes.
- `python -c "from shared.db import migrate; migrate('data/test.db')"` (or equivalent CLI) creates all 8 tables.
- Two processes can write to the same DB concurrently without unhandled `SQLITE_BUSY` (covered by a test).
- No Phase 2+ code, no Docker files yet (Phase 7).

## Constraints / gotchas

- SQLite is shared by 3 future writer processes — the retry wrapper in `shared/db.py` is the single most important deliverable; keep transactions short.
- `fingerprints.chromaprint_vector` is a BLOB (feature vector, not a hash) — see "Fingerprint flow" in `PLAN.md` for why.
- Keep `shared/` import-light (no GPU/ML deps) so every service can import it cheaply.

## Suggested skills

- `tdd` — build `shared/db.py` (migrations + retry wrapper) red-green-refactor.
- `setup-pre-commit` — optional, wire formatting/type-check hooks after scaffold.
- `review` — run a standards+spec review against this doc and `PLAN.md` before finishing.

## After Phase 1

Report back: deliverables list, test results, and any deviations from `PLAN.md`. Next up is Phase 2 (Ingestor) — do not start it.
