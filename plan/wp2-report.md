# WP-2 Report — Ingestor fix-then-ship

**Date:** 2026-06-10  
**Status:** Complete (pending Opus Deep re-review)  
**Routing:** GPT mini (Session 1, Batch 1 — `plan/handoff-batch1-sessions-6165b3.md`)

## Scope

Phase 2 ingestor hardening per Opus fix-then-ship (`plan/work-dispatch-6165b3.md` F1–F7): subprocess timeout, graceful shutdown, partial-chunk rejection, subprocess cleanup, stride test with real WAV bytes, live smoke documentation, and this report.

**Out of scope:** worker/, dashboard/, docker-compose.yml (per session prompt).

## Deliverables

| Item | Path |
|---|---|
| Popen + timeout + process-group kill | `ingestor/ffmpeg.py` |
| WAV duration validation before enqueue | `ingestor/ffmpeg.py`, `ingestor/supervisor.py` |
| SIGTERM/SIGINT → terminate in-flight ffmpeg | `ingestor/__main__.py`, `FfmpegChunkRunner.terminate_active()` |
| Ingestor tests (8) | `tests/test_ingestor.py` |

## Fixes applied

| ID | Change | Evidence |
|---|---|---|
| **F1** | `FfmpegChunkRunner.record_chunk` uses `Popen` + `wait(timeout=duration_sec + 60)`. On timeout: kill process group, return `124`. | `ingestor/ffmpeg.py` |
| **F2** | `terminate_active()` kills tracked Popen; `__main__._shutdown` sets stop event and calls `terminate_active()` on each ingestor runner. | `ingestor/ffmpeg.py`, `ingestor/__main__.py` |
| **F3** | Before enqueue: `is_valid_chunk_duration(path, chunk_len, tolerance=2s)` via stdlib `wave`. Undersized → `log_gap(reason="empty_chunk")`, file removed, no pending row. | `ingestor/supervisor.py` |
| **F4** | `_reap_process()` in `finally` on every `record_chunk` path (success, timeout, kill, error). | `ingestor/ffmpeg.py` |
| **F5** | `test_stride_accounts_for_recording_elapsed_with_valid_wav` — real 90s WAV bytes, `wave.open` duration check, stride sleep `76` (= 83 − 7s capture elapsed). | `tests/test_ingestor.py` |
| **F6** | Live smoke — **done** 2026-06-10 (`plan/ca-tx-ingestor-smoke-20260610.md`: KFI+WBAP, 9 chunks, 0 gaps). | — |
| **F7** | This report. | `plan/wp2-report.md` |

## Test results

```text
$ .venv\Scripts\pytest tests/test_ingestor.py -v
8 passed in 0.78s

$ .venv\Scripts\pytest -q
64 passed, 1 warning in 2.27s
```

### New / updated tests

| Test | Covers |
|---|---|
| `test_is_valid_chunk_duration_uses_two_second_tolerance` | F3 tolerance |
| `test_stride_accounts_for_recording_elapsed_with_valid_wav` | F5 real WAV + elapsed-aware stride |
| `test_partial_wav_logs_empty_chunk_gap_and_does_not_enqueue` | F3 partial rejection |
| `test_ffmpeg_runner_terminate_active_stops_in_flight_process` | F2 terminate in-flight |
| Existing success/backoff tests | Updated `FakeRunner` to write valid WAV (required after F3) |

## Live smoke (F6)

**Skipped.**

- `config/stations.yaml` has a single station (`example-news`) with `enabled: false` and a placeholder URL (`https://example.com/stream.mp3`).
- No reachable live stream configured for a 5-minute ingestor run.
- Manual smoke when a real stream is available: `python -m ingestor data/pipeline.db`, run ~5 min, then query `SELECT COUNT(*) FROM chunks` and `SELECT COUNT(*) FROM gaps`.

## Deviations

None from PLAN Phase 2 or session scope.

## Notes for Opus re-review

- Process-group kill uses `CREATE_NEW_PROCESS_GROUP` on Windows and `os.setsid` elsewhere; `_reap_process` drains/kills on all exit paths.
- Timeout return code `124` is treated as failure → `stream_down` gap + backoff (same as non-zero ffmpeg exit).
- `shared/` unchanged; WAV helpers live in `ingestor/ffmpeg.py` only.

## Next step

Opus Deep re-review WP-2 per `plan/work-dispatch-6165b3.md` Batch 2.
