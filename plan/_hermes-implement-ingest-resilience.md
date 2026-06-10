# Hermes Implement — Ingestor Fast Retry (WP-ingest-resilience)

**Goal:** Stations drop frequently; recover faster by immediate retries before gap+backoff.

**Repo:** `h:\DEV\projects\radio-ad-sensing-pipeline`
**Constraints:** Read `PLAN.md` ingestor section, `AGENTS.md`, project conventions. TDD vertical slices only.

## Problem

`ingestor/supervisor.py` logs a gap and sleeps exponential backoff (5s → max 300s) on every ffmpeg failure. Transient stream drops cause long recovery gaps.

## Scope (WP-A + WP-B only — no probe, no fallback URLs, no long-running ffmpeg)

### 1. Settings (`config/settings.yaml` + `shared/models.py` PipelineSettings)

Add:
```yaml
ingest_immediate_retries: 3
ingest_immediate_retry_delay_sec: 0.5
ingest_backoff_initial_sec: 1
ingest_backoff_max_sec: 30
```

Defaults in PipelineSettings must match.

### 2. Supervisor (`ingestor/supervisor.py`)

- On chunk failure (`stream_down` or `empty_chunk`), retry up to `ingest_immediate_retries` times with `ingest_immediate_retry_delay_sec` sleep between attempts **before** logging gap and entering exponential backoff.
- Each immediate retry is a fresh `run_once` attempt at the same logical cycle OR refactor `run_once` to loop internally — pick the cleaner design; behavior must match tests.
- Exponential backoff uses settings: initial `ingest_backoff_initial_sec`, max `ingest_backoff_max_sec` (replace hardcoded BackoffPolicy defaults 5/300 for production ingestors created via `create_station_ingestors`).
- Success on any immediate retry: reset backoff, enqueue chunk, no gap logged for that cycle.
- After immediate retries exhausted: log **one** gap (not one per retry), then backoff once.

Wire `BackoffPolicy` from settings in `create_station_ingestors`.

### 3. TDD tests (`tests/test_ingestor.py`)

Add/update tests (write failing tests first, then implement):

**test_immediate_retries_recover_without_gap**
- FakeRunner fails twice (returncode=1) then succeeds on 3rd call within same `run_once` cycle.
- Assert: 1 chunk enqueued, 0 gaps, backoff reset.

**test_immediate_retries_exhausted_logs_single_gap**
- FakeRunner fails 4 times when immediate_retries=3.
- Assert: exactly 1 gap with reason stream_down, 0 chunks.

**test_backoff_uses_settings_defaults**
- After exhausted retries, clock sleeps use ingest_backoff_initial_sec then double (1, 2) not (5, 10).
- Update existing `test_failed_ffmpeg_logs_stream_down_gap_and_exponential_backoff` if needed to pass explicit BackoffPolicy or settings.

Keep existing tests green. Run `.venv\Scripts\pytest -q` when done.

### 4. Report

Write `plan/wp-ingest-resilience-report.md` with:
- What changed
- Test evidence (pytest output summary)
- Behavior summary for operators

## Do NOT

- Change ffmpeg reconnect flags (optional minor tweak OK but not required)
- Add fallback URLs or probe
- Touch worker/alerter/dashboard
- Commit secrets
- Skip watching tests fail first (TDD)

## Deliverable

All code + tests + report. pytest 97+ passing (may add new tests).
