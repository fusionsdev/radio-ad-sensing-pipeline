# Pipeline Status Runbook

## Quick check (loan-only)

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
.\scripts\pipeline-loan-ops.ps1
```

## Docker health

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml ps
```

## DB query (live only)

```powershell
docker exec radio-worker python -c "import sqlite3; c=sqlite3.connect('/app/data/pipeline.db'); print(c.execute('SELECT COUNT(*) FROM chunks WHERE status=\"pending\"').fetchone())"
```

## Harness verification

```bash
python tools/harness/run_all.py
```

## Related

- [[Runbooks/Hermes Pipeline Ops]]
- [[02_Operating_Policy]]