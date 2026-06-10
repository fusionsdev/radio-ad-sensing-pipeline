Implemented the WP-5 fix set with a minimal diff. In [worker/dedup.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/dedup.py:222), mismatched normalized phones no longer drag the weighted score down with `0 x 3.0`; the phone weight only applies on an exact normalized match. Category mismatches now contribute `0` instead of `55`, which keeps distinct ads from over-merging.

I added the requested regressions in [tests/test_dedup.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_dedup.py:159), including mangled-phone same-ad merge, distinct ads staying separate, same-station `>180s` incrementing `airing_count`, and cross-station `<3min` counting as two airings. I also wrote [plan/wp5-report.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/wp5-report.md:1) and updated the WP-5 Opus checklist to `ship` in [plan/opus-review-plan-6165b3.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/opus-review-plan-6165b3.md:77).

Verification passed:
- `.venv\Scripts\pytest tests/test_dedup.py -v` → `7 passed`
- `.venv\Scripts\pytest -q` → `69 passed, 1 warning`

