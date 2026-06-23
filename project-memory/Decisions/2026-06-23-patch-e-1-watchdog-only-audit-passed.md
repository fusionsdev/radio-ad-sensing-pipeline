# Decision

Date: 2026-06-23

## Context

After Patch E.1 added fixed_harvest_auto_restart_enabled=false, a controlled watchdog-only audit was run through T+30 with fixed harvest klif-am-570 and wbap-am-820.

## Decision

Keep watchdog running in observe-only fixed-harvest mode after T+30 audit passed. Do not add stations, restart ingestor, scale workers, or enable promotion yet.

## Impact

Watchdog can monitor health without changing station enablement or command queue; next work can focus on longer observation before any station or promotion policy change.

## Rollback

docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml stop watchdog

## Related Files

- `config/settings.yaml`
- `watchdog/recovery.py`
- `project-memory/Latest_Status.md`