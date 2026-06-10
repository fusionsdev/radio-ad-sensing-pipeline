# WP-7b Docker Smoke — Windows GPU Host

**Date:** 2026-06-10  
**Host:** Windows 11 + Docker Desktop + RTX 3090  
**Command:**

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml up -d --build
```

## Fixes applied (uncommitted)

| Item | Why |
|------|-----|
| All `*/Dockerfile` | `COPY README.md` — hatchling metadata needs it |
| `docker-compose.yml` | Ollama healthcheck → `ollama list` (image has no curl) |
| `worker/Dockerfile` | `nvidia-cublas-cu12` + `nvidia-cuda-nvrtc-cu12` + `LD_LIBRARY_PATH` |
| `docker-compose.windows-dev.yml` | **new** — prod named volume (SQLite WAL), dashboard `:8081`, dcgm stub |

## Windows caveats

1. **SQLite bind mount** — `./data` → `disk I/O error` on WAL; use `docker-compose.prod.yml` named volume `pipeline_data`.
2. **Port 8080** — reserved by HTTP.sys; dashboard published on **127.0.0.1:8081**.
3. **dcgm-exporter** — needs Linux `/sys/bus/pci`; stubbed with `busybox sleep` on Windows dev.
4. **fpcalc** — not in worker image; fingerprint warnings only (non-blocking).

## Verification

| Check | Result |
|-------|--------|
| `pipeline-migrate` | exit 0 |
| `ollama-pull` | exit 0; `qwen2.5:7b-instruct-q4_K_M` 4.7 GB |
| `ollama` | healthy; RTX 3090 visible |
| `ingestor` | healthy; KFI+WBAP chunking |
| `worker` | healthy; **medium.en** GPU ASR RTF ~0.05 (90s → ~4–5s) |
| `alerter` | healthy; dry-run (no `.env` tokens) |
| `dashboard` | healthy; http://127.0.0.1:8081/ |
| `prometheus` / `grafana` | up; :9090 / :3000 |
| Docker DB | 2 transcripts, 2 done chunks (growing) |
| `pytest` | 97/97 |

## Linux GPU host (production)

Use `docker-compose.prod.yml` only; skip `windows-dev` override. Bind `./data` works on Linux; dcgm-exporter runs natively.

## Not done this session

- Telegram E2E (no `.env`)
- KNX/WLRN/WGUL URL refresh (no stable public MP3/AAC mounts found)
- Initial git commit (user did not request)
