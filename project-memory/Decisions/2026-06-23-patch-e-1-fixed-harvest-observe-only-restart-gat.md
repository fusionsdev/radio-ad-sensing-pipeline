# Decision

Date: 2026-06-23

## Context

Patch E watchdog-only audit reached T+15 safely for promotion/disable but watchdog still queued restart_station for klif-am-570. Fixed harvest audit pass condition now requires no promote_station, no disable_station, and no restart_station unless explicitly enabled.

## Decision

Add fixed_harvest_auto_restart_enabled default false. In auto_restart_stale_station, fixed_harvest_mode with fixed_harvest_auto_restart_enabled=false records stale/manual_attention state only and returns fixed_harvest_observe_only or manual_attention without enqueueing restart_station, disable_station, or mutating stations.enabled.

## Impact

Next watchdog-only audit can verify health/events-only behavior while preserving fixed two-station harvest and pool locks.

## Rollback

git restore shared/models.py config/settings.yaml watchdog/recovery.py tests/test_watchdog.py

## Related Files

- `shared/models.py`
- `config/settings.yaml`
- `watchdog/recovery.py`
- `tests/test_watchdog.py`