# WP-8 Report — Fingerprint Annotation

**Date:** 2026-06-10
**Status:** Complete
**Routing:** Codex CLI (fix-then-ship from Opus Deep review)

## Scope

Close the three remaining Opus review gaps for Phase 8 fingerprint matching:

1. Reject borderline near-threshold matches around the production `0.88` cutoff.
2. Prove offset-tolerant matching on realistic 90s chunk / 30s clip vectors at multiple offsets.
3. Add a CPU-budget regression guard for matcher cost across 100 candidates.

## Changes

| Item | Path |
|---|---|
| Strict threshold guard (`score == threshold` now rejects) | `worker/fingerprint.py` |
| Borderline near-miss regression test | `tests/test_fingerprint.py` |
| Realistic multi-offset 90s/30s embedding test | `tests/test_fingerprint.py` |
| 100-candidate CPU budget assertion (`< 1.0s`) | `tests/test_fingerprint.py` |

## Behavior verified

- **False-positive guard:** a synthetic window scoring exactly `0.88` no longer matches, so the conservative threshold is strictly greater-than rather than greater-than-or-equal.
- **Offset tolerance:** the same 30s clip embedded inside a 90s chunk matches correctly at offsets `0s`, `30s`, and `45s`, with exact `offset_frames` / `offset_seconds` returned.
- **CPU budget:** the matcher completes a 100-candidate realistic-vector search under the test budget on this host, giving the suite a regression tripwire if performance drifts.

## Verification

```bash
.venv\Scripts\pytest tests/test_fingerprint.py -v
.venv\Scripts\pytest -q
```

Result in this session:

- `.venv\Scripts\pytest tests/test_fingerprint.py -v` — passed (`10/10`)
- `.venv\Scripts\pytest -q` — **83/83 passed** (after WP-11a fixed concurrent retry test)

## Notes

- Diff stayed scoped to fingerprint logic, fingerprint tests, and plan docs only.
- This closes the remaining WP-8 Opus fix list; no further Phase 8 code changes are pending from that review.
