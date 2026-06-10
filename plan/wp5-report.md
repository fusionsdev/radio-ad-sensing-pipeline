# WP-5 Report — Dedup (Phase 5 fix-then-ship)

**Date:** 2026-06-10 (Batch 3 Session A)  
**Status:** Complete (H1, M2 + regression tests)

## Scope

Opus Deep review (`plan/opus-review-plan-6165b3.md`) returned **fix-then-ship** for two dedup scoring issues:

- **H1** phone mismatches were scored as `0 x 3.0`, causing under-merge when ASR mangled the number
- **M2** category mismatches contributed `55`, which was too generous for distinct ads

This pass keeps the fix minimal: only dedup scoring, regression tests, and report/checklist updates.

## Fixes applied

| ID | Issue | Fix |
|---|---|---|
| **H1** | Exact phone mismatch heavily penalized likely same-ad matches | `worker/dedup.py` now only applies phone weight when normalized phones match; mismatches are omitted from the weighted score |
| **M2** | Category mismatch still contributed a mid-score (`55`) | Category mismatch now contributes `0`, preserving category as a real disambiguator |
| **R1** | Missing regression coverage for mangled phones | Added same-ad merge test where phone differs but company/summary still match |
| **R2** | Missing regression coverage for distinct ads | Added mismatch test proving different category/company copy create separate canonicals |
| **R3** | Airing-count boundary behavior not explicit | Added separate tests for same-station `>180s` increment and cross-station `<180s` counting as two airings |

## Key behavior changes

- Dedup no longer relies on exact phone equality to merge likely same ads
- Category mismatch cannot drift a distinct ad toward a fuzzy merge
- Same-station overlap suppression still applies within 180 seconds
- Same-station repeats after 180 seconds increment `airing_count`
- Cross-station detections within the 3-minute window still count as separate airings

## Deliverables

| Item | Location |
|---|---|
| Updated weighted dedup scoring | `worker/dedup.py` |
| Regression tests | `tests/test_dedup.py` (7 tests) |

## Test results

```
.venv\Scripts\pytest tests/test_dedup.py -v   → 7 passed
.venv\Scripts\pytest -q                       → 69 passed
```

New or expanded tests:

- `test_fuzzy_match_reuses_canonical_and_same_station_window_does_not_increment_airings`
- `test_same_ad_after_window_counts_new_airing`
- `test_cross_station_airings_within_window_count_separately`
- `test_distinct_ads_do_not_merge_when_category_differs`

## Verification

```bash
.venv\Scripts\pytest tests/test_dedup.py -v
.venv\Scripts\pytest -q
```

## Deviations

None.
