# WP-13 Production Hardening Report

**Date:** 2026-06-10  
**Plan:** `plan/codexplan.md`  
**Verdict (implementer):** ready for Hermes review gate

## Summary

Implemented production hardening for SQLite WAL maintenance, prod named-volume storage, and an ASR benchmark path without changing default ASR model, fingerprint threshold, or Ollama temperature.

## Deliverables

| Item | Status | Notes |
|------|--------|-------|
| `WalCheckpointResult` + `checkpoint_wal(PASSIVE)` | ✅ | `shared/db.py` |
| Read-only connections skip `journal_mode=WAL` write | ✅ | `get_connection(read_only=True)` |
| Janitor passive checkpoint in `run_sweep()` | ✅ | log+continue on failure |
| WAL Prometheus gauges | ✅ | `pipeline_sqlite_wal_*` in `shared/metrics.py` |
| `docker-compose.prod.yml` | ✅ | `pipeline_data` named volume |
| `ASR_MODEL` / `ASR_COMPUTE_TYPE` env overrides | ✅ | `shared/config.py` |
| `python -m worker.asr_benchmark` | ✅ | fake factory in CI tests |
| Default `medium.en` unchanged | ✅ | `config/settings.yaml` |

## Verify commands

```text
pytest -q                    → 97 passed
docker compose config --quiet → OK
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet → OK
```

## Hermes review gate

**Report:** `plan/hermes-review-wp13-20260610-0846.md`  
**Verdict:** **ship** (5 minor notes, no critical/major)

Minor notes: tautological read-only WAL test, empty ASR env in prod compose (works), gauge last-writer-wins, busy logged at DEBUG.

- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` on GPU host
- [ ] Confirm `/app/data` on `pipeline_data`, `/app/chunks` on tmpfs
- [ ] `python -m worker.asr_benchmark --audio <5-10min.wav> --models medium.en,distil-large-v3 --compute-type int8_float16 --json`

## Files changed

- `shared/db.py`, `shared/metrics.py`, `shared/config.py`
- `worker/janitor.py`, `worker/asr_benchmark.py`
- `docker-compose.prod.yml`
- `tests/test_db.py`, `tests/test_janitor.py`, `tests/test_metrics.py`, `tests/test_asr_benchmark.py`, `tests/test_config.py`
