# Handoff: WP-3 — ASR Worker (Phase 3)

Self-contained brief for Composer 2.5 to implement the ASR worker: a queue consumer that claims pending chunks, transcribes them with faster-whisper, persists transcripts, and enforces the bounded-queue drop-oldest policy.

## Context (read first)

- `PLAN.md` (repo root) — §Architecture, §Implementation Phases item 3, §Key Risks ("ASR throughput has zero headroom at 10 stations").
- `plan/phase1-report.md` — what already exists. Phase 1 is DONE: `shared/db.py` (WAL + `retry_on_busy` + `transaction()`), `shared/models.py`, `shared/config.py`, `shared/logging.py`, migration 001. **Reuse these — do not reimplement.**
- Run `pytest` before starting: 18/18 must pass.

## Scope — WP-3 ONLY

Implement in `worker/` (GPU deps allowed here, NEVER in `shared/`):

1. **`worker/transcribe.py`** — thin wrapper around `faster_whisper.WhisperModel`:
   - `medium.en`, `compute_type="int8_float16"`, configurable via `settings.yaml` (add `asr_model`, `asr_compute_type` keys + extend `PipelineSettings`).
   - Returns full text + **segments with start/end timestamps** (Phase 5 needs them for ad-clip cutting) + wall-clock duration (for RTF metric).
   - Model loaded once per process, lazily.
2. **`worker/consumer.py`** — polling loop:
   - Claim oldest `pending` chunk atomically: `UPDATE chunks SET status='processing' WHERE id = (SELECT id FROM chunks WHERE status='pending' ORDER BY start_ts LIMIT 1) RETURNING id, ...` inside `transaction()` + `retry_on_busy`.
   - On success: insert `transcripts` row (store segments as JSON in a new nullable `segments_json` column — add migration `002_transcript_segments.sql`), set chunk `status='done'`.
   - On failure: set `status='dropped'`, write `error`, log; never crash the loop.
   - Missing audio file on disk → drop with error, continue.
3. **Drop-oldest policy** — before claiming, if pending backlog exceeds `queue_max_hours` (from settings, default 2h, computed from chunk durations or count × chunk_len):
   - Mark the oldest overflow chunks `dropped`, insert a `gaps` row per station-contiguous range with `reason='dropped_backlog'`.
4. **RTF measurement** — log a structured line per chunk: `rtf = asr_wall_time / chunk_audio_duration`. Keep a rolling average in the `status` table (`key='asr_rtf_avg'`). PLAN requires validating RTF in this phase.
5. **Entrypoint** — `python -m worker` runs migrate-if-needed then the consumer loop; clean shutdown on SIGINT/SIGTERM.
6. **Dependencies** — add `faster-whisper` to `pyproject.toml` under a `worker` optional-dependency group (keep base install import-light).

## Tests (no GPU in CI)

- Mock/fake the WhisperModel (inject via constructor or factory) — test consumer claim → transcript insert → status transitions.
- Drop-oldest: seed >2h of pending chunks, assert oldest dropped + `gaps` rows written + newest survive.
- Atomic claim: two consumer threads never process the same chunk.
- Failure path: missing file → `dropped` + `error` set, loop continues.
- All existing 18 tests must still pass.

## Acceptance criteria

- `pytest` green (old + new).
- `python -m worker` starts, polls, exits cleanly on Ctrl+C (manual check OK).
- No imports of faster-whisper at `shared/` level; `import shared.db` works without GPU libs installed.

## Out of scope

- LLM extraction (WP-4), dedup (WP-5), fingerprinting (WP-8), Docker (WP-7), metrics endpoint (WP-10).

## Report back

Write `plan/wp3-report.md`: deliverables, test results, measured/mocked RTF notes, deviations.
