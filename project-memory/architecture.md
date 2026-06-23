# RadioSense Architecture Notes

Quick-reference summary. Canonical detail: `01_Current_Architecture.md`.

## High-Level System

RadioSense is a radio ad sensing pipeline.

Core components:

- Stream ingestion (`ingestor/`)
- Audio chunking
- Transcription (`worker/` — faster-whisper)
- Classifier / keyword detection (`worker/keywords.py`, `scripts/loan_classifier.py`)
- SQLite pipeline DB persistence (`shared/db.py`)
- Dashboard API (`dashboard/`)
- Frontend dashboard (`H:\DEV\github_sandbox\radiosense-aistudio` — `:5150/memory`)
- Watchdog/recovery logic (`watchdog/`)
- Reports and exports (`reports/`, `exports/`)
- Memory API + vault reader (`dashboard/routes/memory.py`, `tools/memory/`)

## Operational Warning

The running Docker container may not match source code if it has not been rebuilt.
Always verify container status when dashboard/API behavior differs from code.

See: `LESSONS_LEARNED.md`, `Runbooks/Memory Dashboard.md`.