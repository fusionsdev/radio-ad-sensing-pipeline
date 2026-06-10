Added WP-10b metrics wiring across the four services and wrote the phase note in [plan/wp10b-report.md](h:/DEV/projects/radio-ad-sensing-pipeline/plan/wp10b-report.md).

What changed:
- Added a lightweight Prometheus helper in [shared/metrics.py](h:/DEV/projects/radio-ad-sensing-pipeline/shared/metrics.py)
- Started `/metrics` exporters on the pinned ports in:
  - [ingestor/__main__.py](h:/DEV/projects/radio-ad-sensing-pipeline/ingestor/__main__.py)
  - [worker/__main__.py](h:/DEV/projects/radio-ad-sensing-pipeline/worker/__main__.py)
  - [alerter/__main__.py](h:/DEV/projects/radio-ad-sensing-pipeline/alerter/__main__.py)
  - [dashboard/main.py](h:/DEV/projects/radio-ad-sensing-pipeline/dashboard/main.py)
- Wired the agreed metric names into the natural service checkpoints:
  - `pipeline_queue_pending_hours`
  - `pipeline_chunks_processed_total{service}`
  - `pipeline_chunks_dropped_total`
  - `pipeline_asr_rtf_avg`
  - `pipeline_station_last_chunk_timestamp_seconds{station}`
- Added `prometheus-client` to [pyproject.toml](h:/DEV/projects/radio-ad-sensing-pipeline/pyproject.toml)

Verification:
- `pytest -q` -> `74 passed`
- Smoked a temporary exporter endpoint and confirmed all expected metric names are present on `/metrics`

If you want, I can do a quick compose-level smoke next to confirm the four service ports line up inside the stack.