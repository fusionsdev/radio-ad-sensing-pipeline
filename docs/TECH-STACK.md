# Tech Stack — Radio Ad-Sensing Pipeline

เอกสารสรุปเทคโนโลยีทั้งหมดที่ใช้ในโปรเจกต์ **Autonomous Radio Ad-Sensing Pipeline** — ระบบ ingest สตรีมวิทยุ News/Talk จากสหรัฐฯ 24/7 แบบ local-first บน GPU box เดียว ตรวจจับโฆษณา loan/funding แล้วแจ้งเตือนผ่าน Telegram

> **แหล่งอ้างอิง:** [`PLAN.md`](../PLAN.md), [`AGENTS.md`](../AGENTS.md), [`pyproject.toml`](../pyproject.toml), [`docker-compose.yml`](../docker-compose.yml)

---

## 1. ภาพรวมสถาปัตยกรรม

```
stations.yaml
     │
     ▼
[ingestor]  ffmpeg ──► chunks/ (WAV บน tmpfs/disk)
     │                      │
     │                      ▼ (SQLite queue: chunks table)
     ▼
[worker]    chromaprint ──► faster-whisper ──► Ollama/Qwen ──► rapidfuzz dedup ──► detections
     │              (CPU)         (GPU)              (GPU)
     ▼
[alerter]   Telegram Bot API (first-seen + ops + daily digest)
[janitor]   (ใน worker) retention, gap detection, WAL checkpoint
[dashboard] FastAPI + Jinja2/HTMX (read-only)
[prometheus] ◄── /metrics จากทุก service + Ollama + dcgm-exporter
[grafana]   dashboards provisioned as code
```

| หลักการ | รายละเอียด |
|---|---|
| Deployment model | Docker Compose บน host เดียว (Ubuntu / Windows Docker Desktop + GPU) |
| Scale target | 4–10 สถานีพร้อมกัน |
| Queue | SQLite `chunks` table — **ไม่ใช้** Redis/Celery |
| Secrets | `.env` (Telegram token) — ไม่ commit |
| ภาษา runtime | Python 3.11+ |

---

## 2. ภาษาและ Runtime

| รายการ | เวอร์ชัน / รายละเอียด |
|---|---|
| **Python** | ≥ 3.11 (`requires-python` ใน `pyproject.toml`) |
| **Package manager** | pip + editable install (`pip install -e ".[dev,dashboard,worker]"`) |
| **Build backend** | Hatchling (`hatchling.build`) |
| **Type hints** | ใช้ทั่วทั้ง codebase (`from __future__ import annotations`) |
| **Virtual env** | `.venv` (local dev) |

### Python dependencies (หลัก)

| Package | บทบาท | Optional extra |
|---|---|---|
| `pydantic` ≥ 2.0 | Schema validation, LLM extraction model | base |
| `pydantic-settings` ≥ 2.0 | Settings loading | base |
| `PyYAML` ≥ 6.0 | `stations.yaml`, `settings.yaml`, keywords | base |
| `prometheus-client` ≥ 0.20 | `/metrics` ทุก service | base |
| `faster-whisper` ≥ 1.0 | ASR (Whisper via CTranslate2) | `worker` |
| `rapidfuzz` ≥ 3.0 | Fuzzy deduplication | `worker` |
| `fastapi` ≥ 0.100 | Dashboard API | `dashboard` |
| `uvicorn[standard]` ≥ 0.23 | ASGI server | `dashboard` |
| `jinja2` ≥ 3.1 | HTML templates | `dashboard` |
| `pytest` ≥ 8.0 | Unit/integration tests | `dev` |
| `httpx` ≥ 0.25 | Test client | `dev` |

Worker image เพิ่ม CUDA wheels: `nvidia-cublas-cu12`, `nvidia-cuda-nvrtc-cu12` สำหรับ CTranslate2 GPU inference

---

## 3. Services (Microservices ใน Compose)

### 3.1 Ingestor (`ingestor/`)

| รายการ | รายละเอียด |
|---|---|
| **หน้าที่** | Supervisor loop ต่อสถานี, เขียน chunk WAV, enqueue SQLite, log gaps |
| **Base image** | `python:3.11-slim` |
| **System deps** | `ffmpeg`, `ca-certificates`, `curl` |
| **GPU** | ไม่ต้องการ |
| **Metrics port** | 9101 |
| **Entrypoint** | `python -m ingestor` |

**ffmpeg** — capture HTTP/HTTPS radio streams, reconnect flags, chunk 90s + overlap 7s (configurable ใน `config/settings.yaml`)

### 3.2 Worker (`worker/`)

| รายการ | รายละเอียด |
|---|---|
| **หน้าที่** | Consumer queue: fingerprint → ASR → LLM extract → dedup → persist + janitor |
| **Base image** | `python:3.11-slim` |
| **System deps** | `ffmpeg`, `libsndfile1`, `curl`, Chromaprint `fpcalc` (optional — non-fatal ถ้าไม่มี) |
| **GPU** | NVIDIA Container Toolkit — แชร์ GPU กับ Ollama |
| **Metrics port** | 9102 |
| **Entrypoint** | `python -m worker data/pipeline.db` |

**Modules สำคัญ:**

| Module | หน้าที่ |
|---|---|
| `fingerprint.py` | Chromaprint vector + sliding-window match กับ known ads |
| `transcribe.py` | faster-whisper wrapper |
| `extract.py` | Ollama HTTP client (`urllib`), JSON schema prompt, phone normalization |
| `dedup.py` | rapidfuzz matching กับ `canonical_ads` |
| `keywords.py` | Loan keyword hits จาก `loan_keywords.yaml` |
| `janitor.py` | ลบ chunk เก่า, WAL checkpoint, gap rollup |

### 3.3 Alerter (`alerter/`)

| รายการ | รายละเอียด |
|---|---|
| **หน้าที่** | First-seen ad alerts, ops alerts (station down >15min, queue drops), daily digest |
| **Integration** | Telegram Bot API — **outbound-only** (`sendMessage`, `sendAudio`) |
| **Dry-run** | ถ้าไม่มี `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` |
| **Metrics port** | 9103 |

### 3.4 Dashboard (`dashboard/`)

| รายการ | รายละเอียด |
|---|---|
| **Framework** | FastAPI + Jinja2 templates + HTMX (progressive enhancement) |
| **Auth** | ไม่มี — read-only, bind LAN/localhost |
| **Routes** | `/`, `/ads`, `/ads/{id}`, `/stations`, `/gaps`, `/audio/{id}`, `/health` |
| **Metrics port** | 9104 |
| **Default port** | 8080 (Docker Windows dev: 8081) |
| **Local dev** | `python -m dashboard` |

### 3.5 Init / Sidecar Services

| Service | Image | หน้าที่ |
|---|---|---|
| `pipeline-migrate` | ingestor image | One-shot SQLite migration |
| `ollama-pull` | `curlimages/curl` | Pull `qwen2.5:7b-instruct-q4_K_M` ก่อน worker start |
| `ollama` | `ollama/ollama:latest` | Local LLM server |
| `prometheus` | `prom/prometheus:latest` | Metrics TSDB (retention 15d) |
| `grafana` | `grafana/grafana:latest` | Dashboards + alerting rules viewer |
| `dcgm-exporter` | `nvcr.io/nvidia/k8s/dcgm-exporter` | GPU metrics (stub บน Windows dev) |

---

## 4. AI / ML Stack

### 4.1 Automatic Speech Recognition (ASR)

| รายการ | ค่า |
|---|---|
| **Engine** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2 backend) |
| **Model** | `medium.en` (config: `asr_model`) |
| **Compute type** | `int8_float16` (config: `asr_compute_type`) |
| **VRAM** | ~1.5 GB |
| **Throughput** | ~10× real-time (single GPU) |
| **Output** | Full transcript + segment timestamps (ใช้ตัด ad clip boundaries) |

### 4.2 Large Language Model (Extraction)

| รายการ | ค่า |
|---|---|
| **Runtime** | [Ollama](https://ollama.com/) |
| **Model** | `qwen2.5:7b-instruct-q4_K_M` (Q4_K_M quantization) |
| **VRAM** | ~5 GB |
| **API** | `POST /api/generate` with JSON schema structured output |
| **Client** | `urllib` (stdlib — ไม่ดึง httpx เข้า worker core) |
| **Schema fields** | `is_ad`, `ad_category`, `company_name`, `phone_number`, `website`, `offer_summary`, `key_claims`, `confidence` |
| **Metadata injection** | `station` / `timestamp` ใส่จาก chunk metadata — **ไม่ถาม LLM** |

### 4.3 Audio Fingerprinting

| รายการ | ค่า |
|---|---|
| **Tool** | Chromaprint via `fpcalc -raw -json` CLI |
| **Storage** | `fingerprints.chromaprint_vector` เป็น **BLOB feature vector** (ไม่ใช่ hash) |
| **Matching** | Offset-tolerant sliding-window correlation |
| **Purpose** | Annotation — skip redundant LLM บน known ads; ASR ยังรันทุก chunk |
| **CPU only** | ไม่ใช้ VRAM |

### 4.4 Deduplication

| รายการ | ค่า |
|---|---|
| **Library** | [rapidfuzz](https://github.com/maxbachmann/RapidFuzz) |
| **Threshold** | 85% (`fuzzy_match_threshold` ใน settings) |
| **Window** | 7 วัน (`dedup_window_days`) |
| **Overlap de-dupe** | Same ad + same station ภายใน 3 นาที = 1 airing |
| **Phone normalization** | Spelled-out digits → numeric (regex + rules ใน `extract.py`) |

---

## 5. Data Layer

### 5.1 Database

| รายการ | ค่า |
|---|---|
| **Engine** | SQLite 3 |
| **Mode** | WAL (`journal_mode=WAL`) |
| **Concurrency** | `busy_timeout=5000ms` + `@retry_on_busy` decorator ใน `shared/db.py` |
| **Writers** | ingestor, worker, alerter (3 processes) |
| **Readers** | dashboard (read-only connections) |
| **Migrations** | SQL files ใน `shared/migrations/` — รัน via `shared.db.migrate()` |
| **Path** | `data/pipeline.db` (prod: Docker named volume `pipeline_data`) |

### 5.2 Core Tables

| Table | หน้าที่ |
|---|---|
| `stations` | สถานีจาก `stations.yaml` |
| `chunks` | Work queue (pending/processing/done/dropped) + `known_ad_id` |
| `transcripts` | ASR output + `segments_json` |
| `canonical_ads` | Ad ที่ dedup แล้ว + archived audio path |
| `detections` | ทุก airing + LLM fields + `alerted` flag |
| `fingerprints` | Chromaprint vectors ของ canonical ads |
| `gaps` | Stream downtime / backlog drops |
| `keyword_hits` | Loan keyword matches |
| `station_daily` | Rolling daily stats |
| `status` | Counters สำหรับ digest/health |

### 5.3 File Storage

| Path | Retention | หมายเหตุ |
|---|---|---|
| `data/chunks/` / `CHUNKS_DIR` | 24–48h (`retention_hours`) | Transient WAV; Docker ใช้ tmpfs 4GB |
| `data/ad_archive/` | ถาวร | Ad clips ที่ตัดจาก chunk |
| `data/pipeline.db` | ถาวร | Transcripts + detections เก็บตลอด |

---

## 6. Infrastructure & Deployment

### 6.1 Container Orchestration

| รายการ | ค่า |
|---|---|
| **Tool** | Docker Compose v2 (`name: radio-ad-pipeline`) |
| **Services** | 10 containers (ingestor, worker, alerter, dashboard, ollama, ollama-pull, migrate, prometheus, grafana, dcgm-exporter) |
| **Network** | `pipeline-internal` (bridge) |
| **Restart policy** | `unless-stopped` (init containers: `no`) |
| **Logging** | `json-file`, max 10MB × 3 files |

### 6.2 Compose Overrides

| File | ใช้เมื่อ |
|---|---|
| `docker-compose.yml` | Base stack |
| `docker-compose.prod.yml` | Named volume `pipeline_data` แทน bind mount `./data` |
| `docker-compose.windows-dev.yml` | Dashboard port 8081, dcgm stub, คู่กับ prod volume |

**คำสั่ง production (Windows GPU host):**

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d
```

### 6.3 GPU Requirements

| รายการ | ค่า |
|---|---|
| **GPU** | NVIDIA ≥ 12 GB VRAM (ทดสอบบน RTX 3090) |
| **Host toolkit** | [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) |
| **VRAM budget** | Whisper ~1.5GB + Qwen ~5GB + overhead ≈ 8GB |
| **GPU sharing** | worker (ASR) + ollama (LLM) + dcgm-exporter บน GPU เดียว |

### 6.4 System Dependencies (Host / Container)

| Tool | ใช้โดย |
|---|---|
| **ffmpeg** | ingestor (stream capture), worker (audio probe/clip) |
| **fpcalc** (Chromaprint) | worker fingerprint (optional) |
| **curl** | healthchecks, ollama-pull |
| **nvidia-smi** | host GPU verification |

---

## 7. Monitoring & Observability

### 7.1 Metrics (Prometheus)

| Scrape target | Port | Metrics ตัวอย่าง |
|---|---|---|
| ingestor | 9101 | chunks enqueued, station uptime, gaps |
| worker | 9102 | ASR/LLM latency histograms, queue depth, detections |
| alerter | 9103 | alerts sent, digest runs |
| dashboard | 9104 | request counts |
| ollama | 11434 | `ollama_*` counters |
| dcgm-exporter | 9400 | GPU util, VRAM, temperature |
| prometheus | 9090 | self-scrape |

**Instrumentation:** `prometheus-client` ใน `shared/metrics.py` — ทุก Python service expose `/metrics`

### 7.2 Dashboards & Alerts

| รายการ | Path |
|---|---|
| Prometheus config | `monitoring/prometheus.yml` |
| Alert rules | `monitoring/alerts.yml` |
| Grafana provisioning | `monitoring/grafana/provisioning/` |
| Dashboard JSON | `monitoring/grafana/dashboards/pipeline.json` (~19 panels, `$station` filter) |

### 7.3 Logging

| รายการ | ค่า |
|---|---|
| **Format** | Structured JSON logs (`shared/logging.py`) |
| **Driver** | Docker json-file (rotated) |
| **Ops alerts** | Telegram (ไม่ใช้ Alertmanager ใน iteration นี้) |

---

## 8. Configuration

### 8.1 Config Files

| File | เนื้อหา |
|---|---|
| `config/stations.yaml` | สถานี (name, url, format, enabled, display_name) |
| `config/settings.yaml` | chunk_len, overlap, thresholds, ASR model, dashboard bind |
| `config/loan_keywords.yaml` | Keyword phrases สำหรับ loan/funding detection |

### 8.2 Environment Variables (`.env`)

| Variable | บทบาท |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | ปลายทางแจ้งเตือน |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | Grafana login |
| `DASHBOARD_HOST` / `DASHBOARD_PORT` | Local dashboard binding |
| `CHUNKS_DIR` | Override chunk storage path (Docker: `/app/chunks`) |
| `OLLAMA_HOST` | Ollama URL (Docker: `http://ollama:11434`) |
| `ASR_MODEL` / `ASR_COMPUTE_TYPE` | Override ASR settings (prod compose) |

---

## 9. External Integrations

| Service | Direction | Protocol | หมายเหตุ |
|---|---|---|---|
| **Radio streams** | Inbound | HTTP/HTTPS (MP3/AAC/HLS) | Operator-maintained URLs |
| **Telegram Bot API** | Outbound | HTTPS REST | ไม่มี inbound webhook |
| **Ollama** | Internal | HTTP `:11434` | ภายใน Docker network |

**Explicitly out of scope:** PostgreSQL, Redis, inbound Telegram commands, cloud LLM APIs, multi-box scaling

---

## 10. Testing & Quality

| รายการ | รายละเอียด |
|---|---|
| **Framework** | pytest ≥ 8.0 |
| **Test count** | 112 tests (ณ 2026-06-10) |
| **Location** | `tests/` (22 test modules) |
| **Coverage areas** | db, dedup, extract, fingerprint, ingestor, alerter, dashboard, metrics, janitor, e2e smoke, extraction eval |
| **Fixtures** | `tests/fixtures/` — sample transcripts, dashboard seed |
| **Verify command** | `.venv\Scripts\pytest` |

---

## 11. Dev Tooling & Agent Skills

เครื่องมือสำหรับ AI-assisted development (ไม่ใช่ runtime ของ pipeline)

### 11.1 Installed Tools

| Tool | ประเภท | หน้าที่ |
|---|---|---|
| [caveman](https://github.com/JuliusBrussee/caveman) | Skill pack | ลด output tokens (`/caveman`, `/caveman-commit`, …) |
| [headroom](https://github.com/chopratejas/headroom) | MCP server | Input token compression |
| [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) | Knowledge graph | Codebase map, `/understand`, auto-update hooks |

### 11.2 Project Skills (`.agents/skills/`)

`diagnose`, `tdd`, `review`, `handoff`, `grill-me`, `grill-with-docs`, `prototype`, `improve-codebase-architecture`, `zoom-out`, `to-issues`, `to-prd`, `triage`, `setup-pre-commit`, `write-a-skill`, `hermes-dispatch`, `pipeline-ops`, `caveman`

### 11.3 Cursor MCP Plugins

| Server | ใช้เมื่อ |
|---|---|
| Context7 | Library docs (faster-whisper, Ollama, FastAPI, pydantic, …) |
| Exa | Live web research |
| Linear / Notion | Issue tracking (optional) |
| Datadog | Production metrics (post-deploy) |

### 11.4 Operator Scripts (`scripts/`)

| Script | หน้าที่ |
|---|---|
| `pipeline-status.ps1` | Query DB ผ่าน Docker worker |
| `setup-understand-auto.ps1` | Auto-update knowledge graph hooks |
| `understand-dashboard.ps1` | เปิด graph explorer |

### 11.5 Hermes (Remote Ops)

| รายการ | Path |
|---|---|
| Context file | `.hermes.md` |
| Cheatsheet | `plan/telegram-ops-cheatsheet.md` |
| Skill | `.agents/skills/pipeline-ops/SKILL.md` |

---

## 12. Port Map

| Service | Host (default) | Container | หมายเหตุ |
|---|---|---|---|
| Dashboard | 127.0.0.1:8080 | 8080 | Windows dev: **8081** |
| Grafana | 127.0.0.1:3000 | 3000 | admin/admin default |
| Prometheus | 127.0.0.1:9090 | 9090 | localhost only |
| Ingestor metrics | — (internal) | 9101 | |
| Worker metrics | — (internal) | 9102 | |
| Alerter metrics | — (internal) | 9103 | |
| Dashboard metrics | — (internal) | 9104 | |
| Ollama | — (internal) | 11434 | + `/metrics` |
| dcgm-exporter | — (internal) | 9400 | |

---

## 13. Repository Layout (Tech-relevant)

```
radio-ad-sensing-pipeline/
├── shared/           # DB, models, config, logging, metrics (import-light, no GPU deps)
├── ingestor/         # ffmpeg supervisor
├── worker/           # ASR + LLM + dedup + janitor
├── alerter/          # Telegram
├── dashboard/        # FastAPI + templates
├── monitoring/       # Prometheus + Grafana as code
├── config/           # YAML runtime config
├── data/             # gitignored — DB, chunks, archives
├── tests/            # pytest suite
├── scripts/          # ops + understand helpers
├── plan/             # phase reports, handoffs
├── docker-compose*.yml
├── pyproject.toml
└── docs/             # เอกสารเทคนิค (ไฟล์นี้)
```

---

## 14. Hardware & Capacity Summary

| Resource | Minimum | Recommended |
|---|---|---|
| GPU VRAM | 8 GB | 12 GB (RTX 3090 class) |
| CPU | Multi-core | 8+ cores (fingerprint + ffmpeg concurrent) |
| RAM | 16 GB | 32 GB |
| Disk | SSD | NVMe สำหรับ SQLite WAL + ad archive |
| Network | Stable broadband | 10 stations × ~128kbps streams |
| OS | Ubuntu 22.04+ (prod) | Windows 11 + Docker Desktop (dev smoke) |

**Queue backpressure:** bounded ~2h (`queue_max_hours`); drop-oldest + gap log + ops alert

---

## 15. สถานะ Implementation (ณ 2026-06-10)

ทุก Work Package (Phase 1–13 + ingest-resilience) **shipped** — 112/112 tests passing, Docker full stack verified บน Windows GPU host

| Phase | สถานะ |
|---|---|
| 1 Scaffold + DB | ✅ |
| 2 Ingestor | ✅ |
| 3–5 Worker (ASR, LLM, Dedup) | ✅ |
| 6 Alerter | ✅ |
| 7 Docker | ✅ |
| 8 Fingerprint | ✅ |
| 9 Dashboard | ✅ |
| 10 Monitoring (Prometheus/Grafana) | ✅ |
| 11 Tests + Hardening | ✅ |
| 12 RAM disk + Janitor | ✅ |
| 13 Production Hardening | ✅ |

---

## 16. เอกสารที่เกี่ยวข้อง

| เอกสาร | เนื้อหา |
|---|---|
| [`PLAN.md`](../PLAN.md) | Architecture, schema, phases, risks |
| [`AGENTS.md`](../AGENTS.md) | Session memory, current state |
| [`README.md`](../README.md) | Quick start, Understand-Anything commands |
| [`final-install-list.md`](../final-install-list.md) | Skills + plugins installed |
| `plan/*.md` | Phase/WP completion reports |

---

*อัปเดตล่าสุด: 2026-06-11 — สร้างจาก codebase และ canonical docs ของโปรเจกต์*
