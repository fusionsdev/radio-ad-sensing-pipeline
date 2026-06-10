Added the WP-11b eval corpus and scorer. The new fixtures live under [tests/fixtures/extraction_eval/manifest.json](h:/DEV/projects/radio-ad-sensing-pipeline/tests/fixtures/extraction_eval/manifest.json) with 4 positive ad transcripts and 3 negative non-commercial segments, and the new scorer test is [tests/test_extraction_eval.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_extraction_eval.py). It uses `normalize_phone_number` plus a mock `OllamaExtractor` backend, so CI stays fully offline while still documenting ground truth for later manual Ollama runs.

I also wrote the phase report at [plan/wp11b-report.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/wp11b-report.md).

Verification:
- `.venv\Scripts\pytest tests/test_extraction_eval.py -v` passed: `3 passed`
- `.venv\Scripts\pytest -q` did not go fully green: `82 passed, 1 failed`

The full-suite failure appears unrelated to WP-11b and is in [tests/test_db.py](h:/DEV/projects/radio-ad-sensing-pipeline/tests/test_db.py:132), where `test_concurrent_writes_retry_on_sqlite_busy` times out waiting on `saw_busy.wait(timeout=5)`.