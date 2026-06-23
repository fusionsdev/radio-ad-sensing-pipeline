# Incident

Date: 2026-06-23

## Symptoms

Patch D deploy recreated ingestor/watchdog at 2026-06-23 03:57 UTC. Within the first audit window, live DB stations.enabled changed from klif-am-570/wbap-am-820 to backup stations (kabc-am-790, then kfi-am-640 promotion attempts), and station_control_commands ids 155-158 showed disable/promote churn.

## Root Cause

Watchdog stale/active calculation enqueued disable_station/promote_station during deploy; Patch D made disable_station a real stations.enabled mutation, so the safety invariant failed immediately.

## Resolution

Rolled ingestor/watchdog images back to pre-patch-d-25690623-105727, restored live DB enabled set to klif-am-570 and wbap-am-820, failed pending promotion commands 157/158, restored station_health/station_pool rows for affected stations from pre-deploy snapshot, and left watchdog stopped to prevent further promotion/disable churn.

## Prevention

Do not redeploy Patch D or start watchdog until disable/promote gating is fixed and tested against stale active-slot scenarios; keep replacement_eligible at 0 and do not add stations until audit passes.

## Related Components

- watchdog
- ingestor
- station_control_commands
- stations
- station_health
- station_pool