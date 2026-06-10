# Telegram Ops Cheatsheet — Radio Ad-Sensing Pipeline

Copy-paste blocks for **Hermes (Telegram Q&A)** or **PowerShell on the Win GPU host**.
Project root: `h:\DEV\projects\radio-ad-sensing-pipeline`

Hermes skill: `/pipeline-ops` → `.agents/skills/pipeline-ops/SKILL.md`

---

## Hermes prompts (type in Telegram)

```
/pipeline-ops status
```

```
สถานะ pipeline ตอนนี้ — queue, stations, keyword hits
```

```
keyword hits top 15 วันนี้
```

```
station ไหน Down / pending เยอะสุด
```

```
review inbox tier A มีกี่รายการ
```

```
worker ยังทำงานอยู่ไหม ดู log ล่าสุด
```

```
cfpb collector รันล่าสุดเมื่อไหร่ มี seed กี่ตัว
```

```
top CFPB company entities score สูงสุด 10
```

```
หลัง reboot ต้อง up stack ยังไง
```

```
git push ยังไม่ได้ — ช่วย add remote
```

---

## Health check (run on host)

**Full status (preferred — live DB inside container):**

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
.\scripts\pipeline-status.ps1
```

**CFPB trademark seed collector (one-shot):**

```powershell
# Host .venv
.\scripts\run-cfpb-collector.ps1

# Docker one-shot (uses compose profile cfpb)
.\scripts\run-cfpb-collector.ps1 -Docker

# Export CSV
.venv\Scripts\python scripts/export_cfpb_brand_candidates.py --min-score 70
```

Dashboard: `http://127.0.0.1:8081/cfpb` (when stack up)

**Docker services:**

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml ps
```

**Queue by status:**

```powershell
docker exec radio-worker python -c "import sqlite3; c=sqlite3.connect('/app/data/pipeline.db'); print(c.execute('SELECT status, COUNT(*) FROM chunks GROUP BY status').fetchall()); c.close()"
```

**Top keyword hits:**

```powershell
docker exec radio-worker python -c "import sqlite3; c=sqlite3.connect('/app/data/pipeline.db'); print(c.execute('SELECT keyword, COUNT(*) n FROM keyword_hits GROUP BY keyword ORDER BY n DESC LIMIT 15').fetchall()); c.close()"
```

**Recent logs:**

```powershell
docker logs radio-worker --tail 20
docker logs radio-ingestor --tail 20
```

---

## After reboot / deploy

**Bring stack up:**

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d
```

**Reload worker (config/loan_keywords.yaml v2, settings.yaml):**

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml restart radio-worker
```

**Rebuild worker (if image does not bind-mount latest code):**

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d --build radio-worker
```

---

## Dashboard URLs (browser on host)

| Page | URL |
|------|-----|
| Overview | http://127.0.0.1:8081 |
| Review inbox | http://127.0.0.1:8081/review |
| Scorecard (7d yield) | http://127.0.0.1:8081/scorecard |
| Keywords matrix | http://127.0.0.1:8081/keywords |

---

## Git (first push — no remote yet)

```powershell
cd h:\DEV\projects\radio-ad-sensing-pipeline
git remote add origin https://github.com/YOUR_USER/radio-ad-sensing-pipeline.git
git push -u origin main
```

**Remote already configured:**

```powershell
git push origin main
```

---

## Pin rules (operator)

```
❌ Do NOT read data\pipeline.db on Windows while Docker ingest is active — bind-mount can be stale.
✅ Always: docker exec radio-worker … or .\scripts\pipeline-status.ps1

Queue = SQLite chunks table (pending/processing/done/dropped). No Redis.

Keyword v2: phrase + confidence from config/loan_keywords.yaml
Records only when confidence >= keyword_min_record_confidence (default 0.6 in settings.yaml)
```

---

## Hermes reply templates

**OK:**

```
Pipeline: OK
• pending X / done Y / dropped Z
• N stations enabled
• keyword_hits: K | detections: D
→ No action needed
```

**Degraded (backlog):**

```
Pipeline: DEGRADED — backlog
• pending 4200 / worker ~1 chunk/min
• 9 stations ingesting in parallel
→ Reduce enabled stations in config/stations.yaml, restart ingestor
```

**Stations Down after restart (common ~20 min):**

```
Pipeline: RECOVERING
• 2 Live / 7 Down — often empty_chunk from ffmpeg cold start
→ Wait 15–20 min; if still Down, check ingestor logs for stream URL errors
```

---

## Keyword v2 quick reference

- Config: `config/loan_keywords.yaml` (~40 phrases, Tier 1–6)
- Threshold: `config/settings.yaml` → `keyword_min_record_confidence: 0.6`
- Confidence stored in `keyword_hits.context_excerpt` as `[confidence=0.85] …`
- Phrases below 0.6 (e.g. `life insurance` 0.55) are discovery-only — not inserted

---

## Related docs

| Doc | Purpose |
|-----|---------|
| `.hermes.md` | Hermes gateway entry (auto-loaded) |
| `.agents/skills/pipeline-ops/SKILL.md` | Full operator runbook |
| `AGENTS.md` | Agent memory / current phase |
| `plan/wp-mvp-keyword-scorecard-report.md` | Keyword scorecard MVP |
| `docs/cfpb-complaint-collector.md` | CFPB trademark seed collector |
| `plan/wp-cfpb-collector-report.md` | CFPB WP completion record |
