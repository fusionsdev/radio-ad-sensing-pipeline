# CA+TX Pipeline Smoke — Ingestor + Worker + Alerter

**Date:** 2026-06-10  
**Scope:** Operator smoke on Windows dev box (not CI)  
**Host:** `H:\DEV\projects\radio-ad-sensing-pipeline`  
**Config:** `config/stations.yaml` — `kfi-am-640` + `wbap-am-820` `enabled: true`

---

## Phase 1 — Ingestor (WP-2 F6)

```powershell
python -c "from shared.db import migrate; migrate('data/pipeline.db')"
python -m ingestor
```

Runtime ~**6 min** (manual stop). Log: `data/smoke-ingestor.log`.

| Metric | KFI AM 640 | WBAP AM 820 |
|--------|------------|-------------|
| Chunks enqueued | **4** | **5** |
| Gap rows | **0** | **0** |
| WAV duration | **90.0 s** each | **90.0 s** each |
| ffmpeg errors | none | none |

**Verdict: PASS** — both streams ingest reliably.

---

## Phase 2 — Worker (ASR → LLM extraction)

### Setup (Windows native)

```powershell
pip install -e ".[worker]"
ollama serve   # if not already running
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen3:8b"   # local substitute; prod uses qwen2.5:7b-instruct-q4_K_M
$env:ASR_DEVICE = "cpu"          # GPU failed: cublas64_12.dll missing on native Windows
$env:ASR_MODEL = "tiny.en"       # smoke-only; prod default medium.en
python scripts/run_worker_until_empty.py
```

Log: `data/smoke-worker.log`

### Results

| Metric | Value |
|--------|-------|
| Chunks `done` | **8** |
| Chunks `dropped` | **2** (missing WAV — janitor removed file after earlier failed GPU attempt; partial KFI file never existed) |
| Transcripts | **8** |
| Detections / canonical ads | **0** (news/traffic talk — no loan ads in sample; expected) |
| ASR RTF (CPU tiny.en) | ~0.03–0.05 |
| Wall time | ~38 s for 8 × 90 s audio |
| Fingerprint (`fpcalc`) | not installed — logged, non-blocking |
| LLM extraction | ran via Ollama; no extraction failures |

Sample transcript (WBAP traffic): *"across North Texas… McKinney is a great area…"*

**Verdict: PASS** — worker pipeline processes live CA+TX chunks end-to-end on CPU smoke settings.

### Code fixes applied for local smoke

- `worker/extract.py` — reads `OLLAMA_HOST` and `OLLAMA_MODEL` from environment (matches Docker intent)
- `scripts/run_worker_until_empty.py` — drain helper with optional `ASR_DEVICE=cpu`, `SMOKE_MAX_CHUNKS`

### Production note

Native Windows ASR with default `medium.en` + `int8_float16` failed (`cublas64_12.dll`). Use **Docker worker** on GPU host (WP-7b) for production ASR, or install CUDA 12 runtime libs on PATH.

---

## Phase 3 — Alerter (dry-run)

```powershell
python -c "from alerter.service import AlerterService; ..."
# TELEGRAM_* unset → dry-run logs only
```

| Alert | Count |
|-------|-------|
| first_seen | 0 |
| ops (queue drops) | 1 |
| digest | 1 |

**Verdict: PASS** — alerter polls DB; ops alert fired for 2 dropped chunks.

---

## Dashboard

```powershell
python -m dashboard
```

http://127.0.0.1:8080/

- `/` — 8 chunks processed today, queue 0
- `/stations` — KFI + WBAP last-chunk ages
- `/ads` — empty (no loan ads detected)

---

## Overall

| Phase | Status |
|-------|--------|
| Ingestor CA+TX | ✅ PASS |
| Worker ASR+LLM | ✅ PASS (CPU smoke model) |
| Alerter dry-run | ✅ PASS |
| Telegram live | ⏭ skipped (no `.env` tokens) |
| Docker full stack | ⏭ open (WP-7b GPU host) |
| Broken URLs (KNX/WLRN/WGUL) | ⏭ operator maintenance |
