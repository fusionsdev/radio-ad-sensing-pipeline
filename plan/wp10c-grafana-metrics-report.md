# WP-10c Report — Grafana Metrics Expansion

**Date:** 2026-06-10  
**Status:** Complete  
**Scope:** Extend WP-10a/10b monitoring with stage-attributed latency, subsystem counters, Ollama scrape, and diagnostic Grafana panels.

## Delivered

### Instrumentation (`shared/metrics.py`)

| Metric | Type | Emitter |
|---|---|---|
| `pipeline_stage_duration_seconds{stage}` | histogram | worker |
| `pipeline_llm_extraction_duration_seconds` | histogram | worker |
| `pipeline_detections_total` | counter | worker/dedup |
| `pipeline_asr_duration_seconds{station}` | histogram | worker |
| `pipeline_asr_rtf{station}` | histogram | worker |
| `pipeline_ingest_chunks_total{station}` | counter | ingestor |
| `pipeline_ingest_errors_total{station,reason}` | counter | ingestor |
| `pipeline_dedup_matches_total{match_type}` | counter | worker/dedup |
| `pipeline_dedup_suppressed_total` | counter | worker/dedup |
| `pipeline_fingerprint_hits_total` | counter | worker |
| `pipeline_fingerprint_errors_total` | counter | worker |
| `pipeline_chunks_by_status{status}` | gauge | worker + dashboard refresh |
| `pipeline_alerts_sent_total{alert_type,outcome}` | counter | alerter |

Stages: `fingerprint`, `asr`, `llm`, `dedup`.

### Infra

- `monitoring/prometheus.yml` — Ollama scrape job enabled
- `monitoring/alerts.yml` — `ASRSlow` uses p95 from `pipeline_asr_rtf` histogram
- `docker-compose.yml` — prometheus `depends_on: ollama`
- `monitoring/grafana/dashboards/pipeline.json` — v4, 19 panels, `$station` template

### Tests

- `tests/test_metrics.py` — helpers + `refresh_chunks_by_status`
- `tests/test_config.py` — Telegram optional settings isolated from `.env` leak

## Verification

```bash
.venv\Scripts\pytest -q
docker run --rm --entrypoint promtool -v ${PWD}/monitoring:/etc/prometheus:ro prom/prometheus:latest check config /etc/prometheus/prometheus.yml
docker run --rm --entrypoint promtool -v ${PWD}/monitoring:/etc/prometheus:ro prom/prometheus:latest check rules /etc/prometheus/alerts.yml
.venv\Scripts\python -c "import json; json.load(open('monitoring/grafana/dashboards/pipeline.json'))"
```

## Operator notes

- Restart `worker`, `ingestor`, `alerter`, `prometheus`, `grafana` after deploy.
- Ollama panel 16 requires Ollama ≥0.5 with native `/metrics`; worker LLM histogram (panel 5) works regardless.
- `pipeline_asr_rtf_avg` gauge retained for legacy dashboards; panel 4 and alerts use histogram.
