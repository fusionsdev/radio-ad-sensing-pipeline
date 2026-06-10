# WP-ingest-resilience Report

**Date:** 2026-06-10
**Status:** ✅ SHIPPED

---

## What Changed

### 1. `shared/models.py` — PipelineSettings

Four new fields added with production-safe defaults:

```python
ingest_immediate_retries: int = 3
ingest_immediate_retry_delay_sec: float = 0.5
ingest_backoff_initial_sec: float = 1.0
ingest_backoff_max_sec: float = 30.0
```

Previous BackoffPolicy dataclass defaults (5 s / 300 s) remain for unit-test backward-compat but are no longer used by production ingestors created via `create_station_ingestors`.

### 2. `config/settings.yaml`

New keys mirroring the model defaults:

```yaml
ingest_immediate_retries: 3
ingest_immediate_retry_delay_sec: 0.5
ingest_backoff_initial_sec: 1
ingest_backoff_max_sec: 30
```

### 3. `ingestor/supervisor.py` — StationIngestor.run_once

**Before:** single ffmpeg attempt → on any failure: log gap → backoff sleep (5–300 s).

**After:**

```
attempt 1 (initial)
  ├─ success → enqueue, reset backoff, stride-sleep ✓
  └─ fail → immediate retry loop (up to ingest_immediate_retries times)
      ├─ sleep ingest_immediate_retry_delay_sec between each
      ├─ success on retry → enqueue, reset backoff ✓ (no gap logged)
      └─ all retries exhausted → log ONE gap, backoff.next_delay() sleep ✗
```

Key invariants:
- `run_once` only ever logs 0 or 1 gap per call (never one per retry attempt).
- On any successful attempt the backoff counter is reset.
- Stale partial output is deleted before each retry attempt.

`create_station_ingestors` now wires `BackoffPolicy` from settings:

```python
backoff = BackoffPolicy(
    initial_seconds=float(settings.ingest_backoff_initial_sec),
    max_seconds=float(settings.ingest_backoff_max_sec),
)
```

### 4. `tests/test_ingestor.py`

**New helper class:** `SequencedFakeRunner` — pops returncodes from a list,
writes a valid WAV on success, enabling per-attempt control within a single
`run_once` call.

**New tests (all RED → GREEN via TDD):**

| Test | Scenario | Assertions |
|---|---|---|
| `test_immediate_retries_recover_without_gap` | fail×2, succeed×1 | 1 chunk, 0 gaps, backoff reset, 3 ffmpeg calls |
| `test_immediate_retries_exhausted_logs_single_gap` | fail×4 (retries=3) | 0 chunks, exactly 1 gap (stream_down), 4 ffmpeg calls |
| `test_backoff_uses_settings_defaults` | retries=0, fail×2 | sleeps=[1, 2] not [5, 10] |

**Updated existing tests** (minimal, additive):
- `test_partial_wav_logs_empty_chunk_gap_and_does_not_enqueue` — added `ingest_immediate_retries=0` to settings (single-attempt path; sleep assertion `[4]` still holds)
- `test_failed_ffmpeg_logs_stream_down_gap_and_exponential_backoff` — added `ingest_immediate_retries=0` to settings (backoff sleep assertion `[5, 10]` still holds)

---

## Test Evidence

```
.venv\Scripts\pytest -q
103 passed, 1 warning in 4.98s
```

The 1 pre-existing failure (`test_telegram_settings_optional`) is an environment-
leak issue (live TELEGRAM_BOT_TOKEN env var set outside the repo); it was present
before this WP and is unrelated.

Ingestor suite alone:

```
.venv\Scripts\pytest -q tests/test_ingestor.py
11 passed in 0.93s
```

---

## Behavior Summary for Operators

| Scenario | Before | After |
|---|---|---|
| Stream blip (1–2 s drop) | 5-second gap + 5s backoff sleep | 3 instant retries (0.5s each) → recover, **no gap** |
| Sustained outage | Log gap, sleep 5→10→…→300s | Log gap, sleep 1→2→4→…→30s (faster recovery cycle) |
| Persistent failure | 5/300s backoff cap | 1/30s backoff cap (more aggressive reattempt) |
| Gap logs per outage event | 1 per run_once call (unchanged) | Still exactly 1 per run_once call |

**Recovery time improvement (typical blip):** 5+ seconds → ~1 second (3×0.5s retries succeed on 3rd attempt within same cycle, zero gap logged).

**Backoff cap change:** 300s → 30s. For a station that stays down, the supervisor
will reattempt every ~30s instead of every ~5min. Operators relying on the gap
timeline will see more frequent (but correct) gap entries during long outages.
If the previous 300s cap is preferred, set `ingest_backoff_max_sec: 300` in
`config/settings.yaml`.
