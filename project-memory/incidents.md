# RadioSense Incidents

Index of outages, bugs, stale containers, stream failures, DB mismatches, dashboard API errors, and recovery actions.

Dated incident notes live in `Incidents/` (Obsidian vault). Agent mistakes and prevention live in `LESSONS_LEARNED.md` (repo root).

## Recent Incidents

| Date | Title | Vault note |
|---|---|---|
| 2026-06-23 | Memory API 404 — stale dashboard container | `Incidents/2026-06-23-memory-api-404-docker.md` |
| 2026-06-23 | Patch D controlled deploy rollback | `Incidents/2026-06-23-incident-patch-d-controlled-deploy-rollback.md` |

## Incident Template

### YYYY-MM-DD — Incident title

**Symptom**

**Affected area**

**Root cause**

**Fix**

**Verification**

**Prevention**

## Logging new incidents

```bash
python tools/memory/incident_logger.py "title" --symptoms "…"
```