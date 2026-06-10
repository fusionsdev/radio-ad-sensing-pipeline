# WP-3 Report — Worker Consumer (Phase 3 + integrated pipeline)

**Date:** 2026-06-10 (revised Session 2)  
**Status:** Complete (fix-then-ship G1–G4)

## Deliverables

| Item | Location |
|---|---|
| faster-whisper wrapper (lazy model, segments + RTF) | `worker/transcribe.py` |
| Queue consumer (claim, drop-oldest, persist, RTF avg) | `worker/consumer.py` |
| **Full pipeline wiring in `create_consumer()`** | `worker/consumer.py` L365–388 |
| Ollama extraction backend (default) | `worker/extract.py` → wired via `OllamaExtractor` |
| Dedup + detection persistence (default) | `worker/dedup.py` → wired via `DetectionPersister` |
| Fingerprint annotation (default) | `worker/fingerprint.py` → wired via `FingerprintAnnotator` |
| Entrypoint (`migrate` + poll loop + SIGINT/SIGTERM) | `worker/__main__.py` |
| `segments_json` column migration | `shared/migrations/002_transcript_segments.sql` |
| ASR settings (`asr_model`, `asr_compute_type`) | `config/settings.yaml`, `shared/models.py` |
| Optional worker deps | `pyproject.toml` `[project.optional-dependencies.worker]` |
| Tests (mocked Whisper, no GPU) | `tests/test_worker_consumer.py` |

## Pipeline flow (`_process_claimed`)

1. Optional fingerprint annotation (before ASR); failures log and continue.
2. Transcribe chunk → persist transcript + `segments_json` → chunk `done`.
3. If fingerprint matched (`known_ad`): skip LLM extraction/dedup; chunk stays `done`.
4. Else if extractor + persister wired: run extraction → dedup/persist detection.
5. Extraction/dedup exception → chunk marked `dropped` with error; transcript already persisted.

## Test results

```
pytest tests/test_worker_consumer.py -v   (10 tests)
pytest -q                                   (full suite)
```

Worker consumer tests cover:

- Claim → transcript insert → `done` status + `segments_json` + RTF avg in `status`
- Extraction + dedup run after transcription when fingerprint has no match
- **Known-ad fingerprint hit → transcribe + `done`, LLM extraction skipped** (G3)
- Drop-oldest: 3h pending → 40 oldest dropped, gap row with `dropped_backlog`, newest survive
- Atomic claim: two threads process 4 chunks with no duplicates
- Missing audio file → `dropped` + error, loop continues
- Transcription failure → `dropped` + error, loop continues
- **Extraction failure → `dropped` + error, transcript retained** (G4)
- Empty queue → `run_once()` returns `False`

Verification:

```bash
.venv\Scripts\pytest tests/test_worker_consumer.py tests/test_dashboard.py -v
.venv\Scripts\pytest -q
.venv\Scripts\python -c "import shared.db; import worker.consumer; print('ok')"
.venv\Scripts\python -m worker   # starts, polls empty queue, exits on Ctrl+C
```

## RTF notes

- Per-chunk structured log: `rtf`, `asr_wall_time_sec`, `chunk_audio_duration_sec` on `chunk transcribed` events.
- Rolling average stored in `status` (`asr_rtf_avg` + `asr_rtf_count`).
- Tests use `FakeTranscriber` with 9s wall / 90s audio → RTF 0.1 (validates metric path without GPU).
- Production RTF validation (PLAN ~10× RT target) requires `pip install -e ".[worker]"` + GPU; deferred to operator manual check.

## Deviations

### G2 — Scope decision: **Option (a) — accept WP-3→5 merge in consumer**

The original WP-3 handoff scoped ASR-only (`create_consumer` with transcriber only). Implementation merged Phases 4–5 and 8 annotation into the same consumer loop, and `create_consumer()` now wires `OllamaExtractor`, `DetectionPersister`, and `FingerprintAnnotator` by default. This matches `PLAN.md` architecture (single worker process: fingerprint → ASR → extract → dedup) and avoids a second factory/queue pass. Tests inject fakes via constructor kwargs when isolating ASR behavior; production entrypoint uses the full factory. No code split to ASR-only default.

### Extraction failure semantics (G4)

On extraction/dedup exception after successful ASR, chunk is marked `dropped` with `error` containing `extraction/dedup failed: …`. Transcript row is **retained** (ASR work is not lost). This aligns with PLAN’s “never loses audio/transcript” principle for fingerprint false positives; downstream failure is surfaced via `dropped` + error for ops visibility rather than silent `done`.

## Next phase

- Opus re-review WP-3 after G1–G4 (Batch 2).
- WP-6 Alerter — Telegram on first-seen detections.
- WP-10b — instrument `pipeline_*` metrics in worker/ingestor.
