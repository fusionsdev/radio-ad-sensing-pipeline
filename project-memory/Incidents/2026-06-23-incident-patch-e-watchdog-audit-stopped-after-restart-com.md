# Incident

Date: 2026-06-23

## Symptoms

During controlled watchdog-only audit, T+15 logs showed watchdog queued restart_station for klif-am-570 after a brief stale detection. No promote_station or disable_station was queued; enabled set stayed klif-am-570 and wbap-am-820; replacement_eligible locks stayed 0; command 159 completed and KLIF returned healthy.

## Root Cause

Patch E blocked promotion and disable actions in fixed_harvest_mode but still allowed auto_restart_on_stale to enqueue restart_station before recovery limits were reached.

## Resolution

Stopped watchdog via docker compose stop watchdog. Post-rollback snapshot showed enabled set unchanged, pool locks intact, no active station_control_commands, pending_hours 0.00.

## Prevention

Patch E.1 should make fixed_harvest_mode observe-only for restart_station too, or add an explicit fixed_harvest_auto_restart_enabled flag default false with tests before the next watchdog audit.

## Related Components

- watchdog
- station_control_commands
- station_health