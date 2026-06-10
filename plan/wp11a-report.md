# WP-11a Report — Tests + Hardening

**Date:** 2026-06-10  
**Status:** Complete

## Scope

- Fixed the DB retry regression test so it deterministically exercises the
  `@retry_on_busy` path on real `SQLITE_BUSY` contention.
- Moved the `json` import in `shared/models.py` to module scope.
- Added an in-process smoke test that runs worker persistence and alerter
  dry-run polling against a temporary SQLite DB.

## Verification

- `.\.venv\Scripts\pytest -q`

## Notes

- The smoke test stays local and fast: no GPU, no live stream, and no new
  heavy dependencies.
