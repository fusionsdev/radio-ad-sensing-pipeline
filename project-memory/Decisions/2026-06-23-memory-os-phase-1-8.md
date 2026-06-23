# Decision

Date: 2026-06-23

## Context

Phase 1.75 delivered read-only Memory Dashboard visibility. Operators needed aggregate metrics, timeline, and category breakdowns without opening Obsidian.

## Decision

Phase 1.8 adds read-only Memory analytics:

**API**

- `GET /api/memory/metrics`
- `GET /api/memory/timeline`
- `GET /api/memory/incidents/analytics`
- `GET /api/memory/decisions/categories`

**UI** (radiosense-aistudio `/memory`)

- Memory Metrics, Timeline, Incident Analytics, Decision Analytics

Categorization via keyword rules in `tools/memory/analytics.py`. No DB writes. No classifier/station/Hermes/ingestor changes.

## Impact

Operators see vault growth, event timeline, and grouped decisions/incidents from the active dashboard.

## Rollback

Remove four routes from `dashboard/routes/memory.py` and analytics sections from `MemoryView.tsx`.

## Related Files

- `tools/memory/analytics.py`
- `tools/memory/vault_reader.py`
- `dashboard/routes/memory.py`
- `tests/test_memory_api.py`
- `tests/test_memory_analytics.py`
- `radiosense-aistudio/src/components/MemoryView.tsx`
- `radiosense-aistudio/src/lib/api.ts`