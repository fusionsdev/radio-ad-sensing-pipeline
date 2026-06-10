# WP-6 Report — Alerter (Phase 6)

**Date:** 2026-06-10 (Batch 3 Session C)  
**Status:** Complete

## Scope

Implemented the outbound Telegram alerter described in `PLAN.md` Phase 6 and `plan/work-dispatch-6165b3.md`:

- first-seen detection alerts
- optional `sendAudio` for archived canonical ad audio
- ops alerts for station-down outages and queue drops
- daily digest
- dry-run behavior when Telegram credentials are missing
- restart-safe `alerted` handling for detections
- real poll loop entrypoint for `python -m alerter`

## What changed

| Area | Change |
|---|---|
| Alerter service | Added `alerter/service.py` with a DB polling service, Telegram Bot API wrapper, and alert-state tracking in `status` |
| Entrypoint | Replaced the stub `alerter/__main__.py` with a real poll loop using signal shutdown handling |
| Config | Updated `shared/config.py` so `TelegramSettings` can be constructed by field name in tests and code |
| Tests | Added `tests/test_alerter.py` with mocked Telegram HTTP coverage for first-seen, ops, digest, and dry-run behavior |

## Behavior details

- First-seen detections are selected from `detections.alerted = 0`
- Message alerts are sent with `sendMessage`
- `sendAudio` is sent when the canonical ad archive path exists
- Successful first-seen delivery marks the detection `alerted = 1`
- Dry-run mode logs alerts instead of calling Telegram and still advances alert state so the loop does not spam
- Station-down alerts are keyed off `gaps` + `stations`, with one alert per outage episode
- Queue-drop alerts are summarized and de-duplicated with a persisted last-id marker
- Daily digest is sent once per UTC day and recorded in `status`

## Verification

```bash
.venv\Scripts\pytest tests/test_alerter.py -v
.venv\Scripts\pytest -q
```

## Test results

- `tests/test_alerter.py`: 5 passed
- full suite: 74 passed

## Notes

- `shared/` stayed import-light; no GPU or ML dependencies were added there.
- No secrets were committed.
