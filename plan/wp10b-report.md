# WP-10b Report — Instrument Metrics

**Date:** 2026-06-10  
**Status:** Complete

## Scope

Added Prometheus `/metrics` exporters for all four Python services on the
ports pinned by WP-10a:

- `ingestor` on `9101`
- `worker` on `9102`
- `alerter` on `9103`
- `dashboard` on `9104`

## Delivered

- Added `shared/metrics.py` as a lightweight Prometheus helper module.
- Wired exporter startup into each service entrypoint.
- Emitted the agreed pipeline metrics without adding heavy work to hot loops.
- Added the `prometheus-client` dependency to `pyproject.toml`.

## Metrics wired

- `pipeline_queue_pending_hours`
- `pipeline_chunks_processed_total{service}`
- `pipeline_chunks_dropped_total`
- `pipeline_asr_rtf_avg`
- `pipeline_station_last_chunk_timestamp_seconds{station}`

## Verification

- `pytest -q` → `74 passed`
- Smoke scrape against a temporary exporter confirmed the expected metric names
  are exposed on `/metrics`.

