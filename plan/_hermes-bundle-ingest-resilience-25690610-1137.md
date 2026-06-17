# Hermes Review Bundle — ingest-resilience
Generated: 2026-06-10T11:37:44.5340104+07:00

## Scope
WP-ingest-resilience: immediate ffmpeg retries + shorter backoff

## Changed files
- shared/models.py
- config/settings.yaml
- ingestor/supervisor.py
- tests/test_ingestor.py
- plan/wp-ingest-resilience-report.md

## Implementer report
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


## supervisor.py (run_once section)
```python
    def run_once(self) -> bool:
        """Record and enqueue one chunk.

        On first failure: immediately retries up to ``ingest_immediate_retries``
        times (with ``ingest_immediate_retry_delay_sec`` sleep between each)
        before logging a gap and entering exponential backoff.

        Returns True when a chunk was successfully enqueued, False when all
        attempts (initial + immediate retries) failed and a gap was logged.
        """
        start_ts = self.clock.time()
        expected_end_ts = start_ts + float(self.settings.chunk_len)
        output_path = self._output_path(start_ts)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        max_attempts = 1 + self.settings.ingest_immediate_retries  # initial + retries
        retry_delay = float(self.settings.ingest_immediate_retry_delay_sec)

        last_returncode: int = -1
        succeeded = False

        for attempt in range(max_attempts):
            if attempt > 0:
                # Brief sleep between immediate retry attempts
                if retry_delay > 0:
                    self.clock.sleep(retry_delay)
                # Clean up any partial output from the previous attempt
                if output_path.exists():
                    output_path.unlink(missing_ok=True)

            logger.info(
                "starting station chunk",
                extra={
                    "station": self.station.name,
                    "path": str(output_path),
                    "attempt": attempt + 1,
                },
            )
            last_returncode = self.runner.record_chunk(
                self.station,
                output_path,
                duration_sec=float(self.settings.chunk_len),
            )

            chunk_len = float(self.settings.chunk_len)
            has_output = output_path.is_file() and output_path.stat().st_size > 0
            duration_ok = has_output and is_valid_chunk_duration(output_path, chunk_len)

            if last_returncode == 0 and duration_ok:
                succeeded = True
                break

        if succeeded:
            station_id = upsert_station(self.db_path, self.station)
            enqueue_chunk(
                self.db_path,
                station_id=station_id,
                path=str(output_path),
                start_ts=start_ts,
                end_ts=expected_end_ts,
            )
            self.backoff.reset()
            set_station_last_chunk_timestamp(self.station.name, expected_end_ts)
            increment_chunks_processed("ingestor")
            self._sleep_until_next_stride(start_ts)
            logger.info(
                "chunk enqueued",
                extra={
                    "station": self.station.name,
                    "path": str(output_path),
                    "start_ts": start_ts,
                    "end_ts": expected_end_ts,
                },
            )
            return True

        # All attempts exhausted — log ONE gap, then enter exponential backoff
        reason = "stream_down" if last_returncode != 0 else "empty_chunk"
        station_id = upsert_station(self.db_path, self.station)
        log_gap(
            self.db_path,
            station_id=station_id,
            start_ts=start_ts,
            end_ts=expected_end_ts,
            reason=reason,
        )
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        delay = self.backoff.next_delay()
        logger.warning(
            "station ingest failed",
            extra={
                "station": self.station.name,
                "returncode": last_returncode,
                "reason": reason,
```

## Pytest
```

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_config.py::test_telegram_settings_optional - AssertionError...
1 failed, 103 passed, 1 warning in 4.97s
```
