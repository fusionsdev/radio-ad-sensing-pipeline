# WP-7a Report — Docker Skeleton

**Date:** 2026-06-10
**Status:** Complete
**Routing:** MiniMax M3 (Light — declarative config, pattern follows compose v2 spec)

## Scope

Compose stack skeleton for all 5 application services + Ollama + one-shot model-pull +
one-shot DB-migrate init container. Each Python service has its own Dockerfile
(declares only the system + Python deps it actually needs).

## Deliverables

| Item | Path |
|---|---|
| Compose stack (7 services) | `docker-compose.yml` |
| Ingestor image | `ingestor/Dockerfile` |
| Worker image (GPU) | `worker/Dockerfile` |
| Alerter image | `alerter/Dockerfile` |
| Dashboard image | `dashboard/Dockerfile` |
| Build context hygiene | `.dockerignore` |

## Services

| Service | Image | GPU | Purpose |
|---|---|---|---|
| `ingestor` | built from `ingestor/Dockerfile` | — | ffmpeg supervisor, chunk writer, gap logger |
| `worker` | built from `worker/Dockerfile` | NVIDIA | faster-whisper + (later) Ollama extraction + dedup |
| `alerter` | built from `alerter/Dockerfile` | — | Telegram outbound alerts + daily digest |
| `dashboard` | built from `dashboard/Dockerfile` | — | FastAPI + HTMX read-only (LAN-only by default) |
| `ollama` | `ollama/ollama:latest` | NVIDIA | LLM server (Qwen2.5-7B Q4_K_M) |
| `ollama-pull` | `curlimages/curl:latest` | — | one-shot: pull Qwen2.5-7B on first boot |
| `pipeline-migrate` | reuses ingestor image | — | one-shot: run `shared.db.migrate()` before services start |

## Networking

- Single internal bridge `pipeline-internal` — services reach each other by name
  (`http://ollama:11434`, `http://dashboard:8080` for service-to-service probes).
- Dashboard port `8080` is **bind-published to 127.0.0.1 only** on the host
  (LAN-only by design; PLAN §"Dashboard exposure").

## Volumes

- `./data:/app/data` (bind) — SQLite db, `chunks/`, `ad_archive/`. Survives
  `docker compose down` (host directory persists) and image rebuilds.
- `./config:/app/config:ro` (bind, read-only) — stations.yaml + settings.yaml
  can be tweaked on the host without rebuilding the image.
- `ollama_data:/root/.ollama` (named) — model weights persist across restarts
  but live in Docker's volume store (large, separate from source code).

## Healthchecks (each runs every 30s, 3 retries, 10s start grace)

- `ingestor`: `python -c "from shared.config import load_stations; load_stations()"`
- `worker`: `python -c "import faster_whisper"` (lighter than transcribing audio)
- `alerter`: `python -c "import alerter; from shared.config import load_telegram_settings; load_telegram_settings()"` (import-only; token optional for WP-6 dry-run)
- `dashboard`: `curl -fsS http://127.0.0.1:8080/health`
- `ollama`: `curl -fsS http://127.0.0.1:11434/api/tags`

## Restart policy

All long-running services use `restart: unless-stopped`. The two init containers
(`pipeline-migrate`, `ollama-pull`) use `restart: "no"` — they run once and exit.

## Build verification (M3 verify command)

```bash
$ docker compose config --quiet
exit=0

$ docker compose config --services
pipeline-migrate
ingestor
ollama
ollama-pull
worker
alerter
dashboard
```

## Out of scope (deferred)

- **Compose push to registry** — local images tagged `radio-ad-pipeline/<svc>:dev`.
- **`docker compose up` smoke test** — not run in this session; the host has no
  NVIDIA container toolkit installed, and the worker + ollama services need it.
  WP-7b (operator) will run the live `docker compose up` + GPU sanity check.
- **Per-service healthcheck tuning** — current checks prove the process is alive,
  not that it's doing real work. Will be revisited in WP-10b once metrics are
  instrumented (e.g., replace worker's import check with `promtool`-like probe
  of `/metrics`).
- **Production hardening** — no read-only root FS, no non-root user, no secrets
  beyond .env. Compose is dev-first per PLAN's "single Ubuntu host" scope.
- **GPU reservation in CI** — `deploy.resources.reservations.devices` is only
  honoured by Docker Swarm / Compose v2 with the NVIDIA runtime plugin.

## Deviations from handoff intent

- Worker pulls faster-whisper at build time (`pip install -e ".[worker]"`).
  Image will be ~1.5GB+. Not optimal, but matches Phase 1's "import-light
  shared/" rule: the dep lives in the worker image, not in shared/.
- `ollama-pull` uses a generic `curlimages/curl` image rather than the official
  Ollama one — saves ~3GB on the init container, and `ollama pull` is just
  an HTTP call to the running ollama service.
- **F6 fix-then-ship (2026-06-10):** Alerter healthcheck no longer asserts
  `telegram_bot_token` present. Import-only check allows container healthy in
  dry-run mode before WP-6. Added `alerter/__main__.py` stub (logs + poll loop).
- **F5 fix-then-ship (2026-06-10):** `load_settings()` overlays
  `DASHBOARD_HOST` / `DASHBOARD_PORT` from environment so compose env vars
  actually affect dashboard bind address.

## Next

- WP-7b (operator, GPT mini) — `docker compose up` smoke test on the GPU host,
  NVIDIA runtime sanity, model-pull observation.
- WP-10a (this agent, M3) — Prometheus + Grafana compose services and provisioning.
