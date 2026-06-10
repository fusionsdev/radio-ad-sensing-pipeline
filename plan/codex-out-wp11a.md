Implemented the WP-11a hardening pass and verified the whole suite.

What changed:
- `tests/test_db.py:89` now deterministically proves the `@retry_on_busy` path by holding a real SQLite write lock with `BEGIN IMMEDIATE`, forcing the worker connection to use `timeout=0.0`, and unblocking the retry only after the first `SQLITE_BUSY` is observed.
- `shared/models.py:5` moved `import json` to module scope and `parse_key_claims_json()` now uses the module import.
- `tests/test_e2e_smoke.py:101` adds an in-process smoke test that runs:
  - pending chunk seed in tmp DB
  - `ChunkConsumer` with `FakeTranscriber`
  - real `DetectionPersister`
  - dry-run `AlerterService`
  - assertion that the detection gets alerted
- `plan/wp11a-report.md:4` added the brief batch report.

Verification:
- `.\.venv\Scripts\pytest -q` → `83 passed, 1 warning`

One existing warning remains from Starlette/httpx deprecation in FastAPI’s test client; the tests still pass cleanly.