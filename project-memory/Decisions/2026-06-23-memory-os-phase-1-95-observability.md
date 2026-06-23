# Decision

Date: 2026-06-23

## Context

Add metrics collection, analytics reports, observability harness, and Memory Analytics dashboard section before Phase 2 zvec.

## Decision

Introduce project-memory/Metrics/, metrics_collector/report/models, observability_harness, /api/memory/analytics, Memory Analytics UI. Read-only sources only. No classifier/station/ingestor/DB changes.

## Impact

TBD

## Rollback

Revert related files to prior commit.

## Related Files

- `tools/memory/metrics_collector.py`
- `tools/memory/metrics_report.py`
- `tools/memory/metrics_models.py`
- `tools/harness/runners/observability_harness.py`
- `dashboard/routes/memory.py`
- `tools/memory/vault_reader.py`