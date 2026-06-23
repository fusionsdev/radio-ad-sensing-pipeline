# Handoff — CFPB Collector (2026-06-11)

**Next session:** อ่านไฟล์นี้ + `AGENTS.md` — **อย่าพึ่ง chat history ยาว**

## Done ✅

- WP-CFPB: migrations 006/007, `collectors/`, dashboard `/cfpb`, export, docs
- Ops: `run-cfpb-collector.ps1`, Docker profile `cfpb`, pipeline-status CFPB section
- Auto-approve: `auto_approve_enabled: true`, min score 85 (company-field only; `ad_copy_allowed` still false)
- Tests: **171/171** pytest

## Not done ⏳

- First real CFPB API collect run
- Git commit/push (many untracked on `main`)

## Run next

```powershell
.venv\Scripts\python -c "from shared.db import migrate; migrate('data/pipeline.db')"
docker compose build ingestor worker
.\scripts\run-cfpb-collector.ps1 -Docker
# review → http://127.0.0.1:8081/cfpb/candidates?min_score=70
```

## Skills to invoke (every new chat)

| Trigger | Skill |
|---|---|
| Pipeline status / Telegram | `/pipeline-ops` |
| Session start | Read `AGENTS.md` + this handoff |
| Before commit | `review` |
| Bug | `diagnose` |

## Key paths

- Config: `config/cfpb_collector.yaml`, `config/trademark.yaml`
- Report: `plan/wp-cfpb-collector-report.md`
- Docs: `docs/cfpb-complaint-collector.md`
