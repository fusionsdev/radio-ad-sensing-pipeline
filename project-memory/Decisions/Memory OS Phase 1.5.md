# Decision: Memory OS Phase 1.5

**Date:** 2026-06-23  
**Status:** Accepted

## Context

Phase 1 delivered static project memory. Agents still had to manually create decision and incident notes. Behavioral changes (classifier, station policy, dashboard routing) could ship without documentation.

## Decision

Phase 1.5 adds self-updating memory tooling:

1. **Loggers** — `tools/memory/decision_logger.py`, `incident_logger.py`, `station_logger.py`
2. **Behavior registry** — `tools/memory/baselines/behavior_registry.json` fingerprints classifier, station policy, dashboard routing
3. **Harnesses** — `decision_harness` (undocumented changes fail), `memory_harness` (vault health)
4. **Report** — Memory Health section in `tools/harness/reports/latest.md`
5. **AGENTS.md** — mandatory memory updates when behavior/policy/stations/classifier/architecture changes

## Impact

- Project memory grows automatically via CLI loggers
- Undocumented behavioral drift fails harness validation
- Vault freshness, empty sections, and broken wikilinks are monitored

## Rollback

Remove `decision_harness` and `memory_harness` from `run_all.py`; delete `tools/memory/baselines/`.

## Related Files

- `tools/memory/decision_logger.py`
- `tools/memory/incident_logger.py`
- `tools/memory/station_logger.py`
- `tools/memory/memory_report.py`
- `tools/memory/behavior.py`
- `tools/harness/runners/decision_harness.py`
- `tools/harness/runners/memory_harness.py`
- `tools/harness/run_all.py`
- `AGENTS.md`

## Related

- [[Decisions/Memory OS Phase 1]]
- [[01_Current_Architecture]]