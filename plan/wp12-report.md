# WP-12 Report — Ingestion & RAM Disk Storage

**Date:** 2026-06-10  
**Status:** Complete

## Scope

Post-gate enhancement per WP-12 plan:

- Configurable `chunks_dir` for transient WAV storage (YAML + `CHUNKS_DIR` env)
- Shared **tmpfs** volume between `ingestor` and `worker` in Docker Compose (4 GB)
- **Janitor** in worker for chunk file cleanup (fills PLAN.md gap — janitor was documented but not implemented)

**Out of scope:** WP-2 ingestor logic (F1–F7 shipped), queue/drop-oldest (WP-3), moving SQLite or `ad_archive/` to RAM.

## Deliverables

| Item | Path |
|---|---|
| `chunks_dir` setting + env override | `shared/models.py`, `config/settings.yaml`, `shared/config.py` |
| Ingestor wired to settings | `ingestor/__main__.py` |
| Janitor module | `worker/janitor.py` |
| Consumer integration + periodic sweep | `worker/consumer.py` |
| Janitor metric | `shared/metrics.py` (`pipeline_chunk_files_deleted_total`) |
| Docker tmpfs volume | `docker-compose.yml` |
| Tests (6 new) | `tests/test_janitor.py`, `tests/test_config.py` |
| Env doc comment | `.env.example` |

## Janitor rules

| Action | When |
|---|---|
| Post-process delete | After `_process_claimed` completes (transcribe + extract/dedup path done) |
| Stale pending | `status='pending'` and `start_ts < now - retention_hours` → dropped + gap `retention_expired` |
| Dropped cleanup | Delete WAV for rows already `dropped` (periodic sweep) |
| Orphan sweep | Files under `chunks_dir` with no matching `chunks.path` row |
| Protected | Never delete paths under `ad_archive/` |

Periodic sweep runs every 60 consumer loops (`JANITOR_SWEEP_INTERVAL`).

## Docker tmpfs

- Volume `chunk-tmpfs`: 4 GB tmpfs, mode 1777
- Mounted at `/app/chunks` on **ingestor** and **worker**
- `CHUNKS_DIR=/app/chunks` in compose env
- `./data:/app/data` unchanged — SQLite + `ad_archive/` stay persistent

**RAM budget:** 90 s mono 16 kHz WAV ≈ 2.9 MB/chunk; 10 stations × 2 h queue cap ≈ 2.5 GB peak → 4 GB headroom.

## Test results

```text
$ .venv\Scripts\pytest -q
90 passed, 1 warning in 4.44s

$ docker compose config --quiet
(exit 0)
```

## Deviations

None.

## Manual verify (GPU host)

```bash
docker compose up -d ingestor worker
docker compose exec ingestor ls -la /app/chunks
docker compose exec ingestor mount | grep chunks   # confirm tmpfs
# after ingest + worker processing: WAVs disappear from /app/chunks
ls data/ad_archive/   # ad clips persist on bind mount
```

## Next

Optional operator smoke: WP-2 F6 live ingestor against enabled stream in `config/stations.yaml`.
