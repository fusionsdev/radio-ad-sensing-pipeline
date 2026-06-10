# Ingest Resilience Smoke — Post WP-ingest-resilience

**Date:** 2026-06-10  
**Runtime:** ~4.3 min (`python -m ingestor`)  
**Log:** `data/smoke-ingest-resilience-20260610.log`  
**Config:** `config/settings.yaml` immediate retries enabled (3 × 0.5s, backoff 1–30s)

## KFI AM 640

**Not exercised** — `enabled: false` in `config/stations.yaml` (empty_chunk loop on Docker host; disabled 2026-06-10). Re-enable after stream URL fix to re-run CA smoke.

## WBAP AM 820

| Metric | Value |
|--------|-------|
| Chunks enqueued (smoke window) | **3** |
| Gap rows | **0** |
| ffmpeg errors in log | none |
| Immediate retries observed | none (stable stream) |

**Verdict: PASS** — WBAP ingests reliably with new supervisor logic.

## Retry behavior observed (other enabled stations)

| Station | Observation |
|---------|-------------|
| `whbo-1040` | `attempt: 2` logged — immediate retry path exercised; later chunk enqueued |
| `wsb-am-750` | `attempt: 2` logged during smoke window |

Confirms inline retries fire on transient failure without logging a gap when recovery succeeds on retry.

## pytest (pre-smoke)

```
tests/test_ingestor.py — 11/11 passed
```

## Operator note

Smoke ran **9 enabled stations** concurrently (not only WBAP). For focused CA+TX regression, set only `kfi-am-640` + `wbap-am-820` `enabled: true` after KFI URL is fixed.
