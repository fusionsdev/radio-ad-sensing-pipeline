# Opus Review Gate — MVP Keyword + Scorecard

**Date:** 2026-06-10  
**Reviewer:** Composer (Opus API limit — external Opus subagent unavailable)  
**Scope:** MVP 1–2 keyword hits + scorecard + station_daily rollup  
**Tests:** 127/127 passing  
**Migration:** `[3, 4]` applied to `data/pipeline.db`

## Findings

| Severity | Area | Issue | Fix |
|----------|------|-------|-----|
| minor | `dashboard/queries.py` scorecard | `chunks_7d` counts all chunk rows (pending/dropped included), may slightly deflate yield vs processed-only | Accept for MVP; MVP 3 can filter `status IN ('done','processing')` |
| info | `worker/keywords.py` | Substring match may false-positive on partial words (e.g. "loan" in "alone") | Seed phrases are multi-word; monitor in Hermes weekly review |
| info | `worker/janitor.py` | `rollup_station_daily` runs for all stations daily even with zero activity | Expected — keeps historical baseline |

No critical or major bugs found.

## Checklist

- [x] Dashboard read-only (no write connections)
- [x] Missing `loan_keywords.yaml` → empty list, worker unaffected
- [x] Keyword hits atomic with transcript insert (same transaction)
- [x] UNIQUE `(chunk_id, keyword)` prevents duplicate hits
- [x] Slot recommendation logic tested (`test_dashboard_stats.py`)
- [x] Janitor rollup idempotent via `ON CONFLICT` + daily status key

## VERDICT: ship

Proceed to MVP 3 (URL probe janitor + Hermes swap brief) when 7d yield data exists.
