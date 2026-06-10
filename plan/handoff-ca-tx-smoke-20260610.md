# Handoff — CA+TX Operator Smoke Session

**Date:** 2026-06-10  
**Prior session:** ingestor + worker + alerter dry-run on Windows dev box  
**Smoke report:** `plan/ca-tx-ingestor-smoke-20260610.md`

## Goal achieved

Closed **WP-2 F6** (live ingestor smoke) and extended to **worker + alerter** on real KFI/WBAP streams.

## What changed (uncommitted)

| Path | Change |
|------|--------|
| `config/stations.yaml` | US station catalog; **`kfi-am-640` + `wbap-am-820` enabled: true** |
| `worker/extract.py` | `OLLAMA_HOST`, `OLLAMA_MODEL` from env |
| `scripts/run_worker_until_empty.py` | **new** — drain pending queue; `ASR_DEVICE=cpu`, `SMOKE_MAX_CHUNKS` |
| `plan/ca-tx-ingestor-smoke-20260610.md` | **new** — full smoke record |
| `plan/wp2-report.md` | F6 marked done |
| `AGENTS.md` | 97 tests, WP-13, smoke status |
| `data/pipeline.db` | live smoke DB (8 done, 2 dropped chunks) |
| `data/chunks/` | mostly deleted by janitor after worker |
| `data/smoke-*.log` | operator logs |

Repo still **no git commits** (all files untracked at session start).

## Runtime state

- **DB:** `data/pipeline.db` — 8 transcripts, 0 detections, queue 0
- **Dashboard:** `python -m dashboard` → http://127.0.0.1:8080/
- **Ollama:** local `127.0.0.1:11434`; smoke used `qwen3:8b` (not prod `qwen2.5:7b-instruct-q4_K_M`)
- **ASR native Windows:** GPU fails (`cublas64_12.dll`); smoke used CPU `tiny.en`
- **fpcalc:** not installed — fingerprint warnings only

## Station URL maintenance

| Station | Status |
|---------|--------|
| KFI, WBAP | ✅ verified |
| KABC | ✅ URL works; disabled |
| WHBO | ✅ `ice41.securenetsystems.net/WHBO`; disabled |
| KNX, WLRN, WGUL | ❌ dead URLs — need operator refresh |

## Next session (recommended order)

1. **WP-7b** — `docker compose up -d` on GPU host; verify all services + `medium.en` ASR
2. **Telegram E2E** — `.env` with `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`; rerun ingestor until ad-heavy segment or use eval fixtures
3. **Station URLs** — fix KNX (Audacy), WLRN, WGUL; optional enable FL smoke
4. **Git** — initial commit if user wants version control
5. **Optional:** install `fpcalc` (chromaprint) on operator host; pull prod Ollama model

## Verify before claiming done

```powershell
.venv\Scripts\pytest -q
python -c "from shared.db import migrate; migrate('data/pipeline.db')"
docker compose config --quiet
```

## Suggested skills

| Skill | When |
|-------|------|
| `handoff` | end of next session |
| `diagnose` | stream/ASR/Ollama failures |
| `review` | before first git commit |
| `hermes-dispatch` | before merge if branch exists |
