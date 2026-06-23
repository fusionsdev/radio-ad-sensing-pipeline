# Decision

Date: 2026-06-23

## Context

Watchdog startup previously synced disabled YAML stations into station_pool as replacement_eligible=1, then auto-promoted backups and disabled stale KLIF during a fixed two-station harvest.

## Decision

Add fixed_harvest_mode, fixed_harvest_station_ids, and auto_promotion_enabled settings; require explicit replacement eligibility; preserve pool locks during fixed harvest sync; block auto-promotion in fixed harvest; require auto_promotion_enabled outside fixed harvest; record manual_attention instead of disable_station when fixed harvest reaches recovery limits.

## Impact

Watchdog can be started for observation/audit without promoting backups or disabling fixed-harvest stations while KLIF/WBAP remain the intended temporary harvest set.

## Rollback

git restore shared/models.py config/settings.yaml watchdog/__main__.py watchdog/pool.py watchdog/promotion.py watchdog/recovery.py tests/test_watchdog.py tests/test_watchdog_pool.py

## Related Files

- `shared/models.py`
- `config/settings.yaml`
- `watchdog/__main__.py`
- `watchdog/pool.py`
- `watchdog/promotion.py`
- `watchdog/recovery.py`
- `tests/test_watchdog.py`
- `tests/test_watchdog_pool.py`