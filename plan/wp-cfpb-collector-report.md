# WP-CFPB Collector Report

**Date:** 2026-06-11  
**Scope:** CFPB Consumer Complaint Trademark Collector + Trademark Layer foundation

## Shipped

| Component | Path |
|---|---|
| Trademark migration | `shared/migrations/006_trademark_layer.sql` |
| CFPB migration | `shared/migrations/007_cfpb_collector.sql` |
| Config | `config/cfpb_collector.yaml`, `config/trademark.yaml` |
| Collector package | `collectors/` (API + bulk CSV, normalizer, extractor, scorer, bridge) |
| Dashboard | `/cfpb/*` routes + templates |
| Export | `scripts/export_cfpb_brand_candidates.py` |
| Ops scripts | `scripts/run-cfpb-collector.ps1`, `pipeline_status_query.py` CFPB section |
| Docker | `cfpb-collector` service — compose profile `cfpb` |
| Docs | `docs/cfpb-complaint-collector.md` |
| Tests | `tests/test_cfpb_*.py`, dashboard + config updates — **166/166** |

## Verification

```powershell
.venv\Scripts\pytest
.venv\Scripts\python -c "from shared.db import migrate; migrate('data/test.db')"
```

## Operator commands

```powershell
.\scripts\run-cfpb-collector.ps1              # host .venv
.\scripts\run-cfpb-collector.ps1 -Docker      # compose profile cfpb
.venv\Scripts\python scripts/export_cfpb_brand_candidates.py --min-score 70
python -m dashboard                           # → /cfpb
```

## Constraints honored

- SQLite WAL only — no PostgreSQL/Redis
- No cloud LLM in collector path
- No auto-approval of CFPB candidates
- No Google Ads upload
- Batch job — not in GPU worker hot path

## Follow-up (optional)

- Schedule daily API incremental via Windows Task Scheduler → `run-cfpb-collector.ps1 -Docker`
- Rebuild images after pull: `docker compose build ingestor worker`
- Tune narrative regex after reviewing first production sample
