WP-8 is shipped. I made the threshold guard strict in [worker/fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/fingerprint.py:91), so a score exactly at `0.88` is rejected instead of matching. I also added the three missing acceptance checks in [tests/test_fingerprint.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_fingerprint.py:134): the borderline near-miss guard, realistic 90s/30s multi-offset matches at `0s`, `30s`, and `45s`, and a CPU-budget assertion for 100 candidates.

I wrote the completion report in [plan/wp8-report.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/wp8-report.md:1) and updated the Opus checklist to mark WP-8 as shipped in [plan/opus-review-plan-6165b3.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/opus-review-plan-6165b3.md:81). The diff stayed within the allowed scope.

Verification:
- `.venv\Scripts\pytest tests/test_fingerprint.py -v` passed `10/10`
- `.venv\Scripts\pytest -q` still fails on unrelated existing test `tests/test_db.py::test_concurrent_writes_retry_on_sqlite_busy`

If you want, I can take the next pass on that SQLite concurrency test without touching WP-8.