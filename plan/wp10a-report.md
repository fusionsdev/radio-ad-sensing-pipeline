# WP-10a Report — Monitoring Config (Prometheus + Grafana + DCGM)

**Date:** 2026-06-10
**Status:** Complete
**Routing:** MiniMax M3 (Light — declarative config, standard compose+prometheus+grafana patterns)

## Scope

Prometheus + Grafana + dcgm-exporter wired into the existing compose stack from
WP-7a. Alert rules + Grafana dashboard provisioned as code (no UI clicks
required on first boot).

## Deliverables

| Item | Path |
|---|---|
| Prometheus scrape config | `monitoring/prometheus.yml` |
| Alert rules (4 groups, 7 rules) | `monitoring/alerts.yml` |
| Grafana datasource provisioning | `monitoring/grafana/provisioning/datasources/prometheus.yml` |
| Grafana dashboard provider | `monitoring/grafana/provisioning/dashboards/default.yml` |
| Grafana dashboard (10 panels) | `monitoring/grafana/dashboards/pipeline.json` |
| Compose services (prometheus, grafana, dcgm-exporter) | appended to `docker-compose.yml` |
| Grafana admin password env | appended to `.env.example` |

## Metric naming convention (followed by WP-10b)

The dashboard and alert rules pin a fixed metric namespace. WP-10b **must** emit
these exact metric names in each service:

| Metric | Type | Emitted by | Labels |
|---|---|---|---|
| `pipeline_queue_pending_hours` | gauge | worker (or ingestor) | — |
| `pipeline_chunks_processed_total` | counter | worker | `service` |
| `pipeline_chunks_dropped_total` | counter | worker | — |
| `pipeline_asr_rtf_avg` | gauge | worker | — |
| `pipeline_llm_extraction_duration_seconds` | histogram | worker (later WP) | — |
| `pipeline_detections_total` | counter | worker (later WP) | — |
| `pipeline_station_last_chunk_timestamp_seconds` | gauge | ingestor | `station` |
| `DCGM_FI_DEV_GPU_UTIL` | gauge | dcgm-exporter | `gpu` |
| `DCGM_FI_DEV_FB_USED` / `DCGM_FI_DEV_FB_FREE` | gauge | dcgm-exporter | `gpu` |
| `DCGM_FI_DEV_GPU_TEMP` | gauge | dcgm-exporter | `gpu` |

The `service` label on `pipeline_chunks_processed_total` is what feeds the
"Chunks processed / hour (by service)" panel — WP-10b must label the worker
counter with `service="worker"` and the alerter's analogous counter with
`service="alerter"`.

## Service ports (/metrics endpoints)

These must be exposed by WP-10b in each service via `prometheus_client.start_http_server`:

| Service | Port | Rationale |
|---|---|---|
| ingestor | 9101 | Convention: node_exporter-style |
| worker | 9102 | One above ingestor |
| alerter | 9103 | One above worker |
| dashboard | 9104 | One above alerter |

## Compose additions

| Service | Image | GPU | Port (host) |
|---|---|---|---|
| `prometheus` | `prom/prometheus:latest` | — | `127.0.0.1:9090` |
| `grafana` | `grafana/grafana:latest` | — | `127.0.0.1:3000` |
| `dcgm-exporter` | `nvcr.io/nvidia/k8s/dcgm-exporter:latest` | NVIDIA | — (scraped internally on `:9400`) |

Both `prometheus` and `grafana` bind to `127.0.0.1` on the host (LAN-only,
matching the dashboard's exposure model — see PLAN §"Dashboard exposure").

## Verification (M3 verify commands)

```bash
$ docker compose config --quiet
(exit 0, no output)

$ docker compose config --services
pipeline-migrate
dashboard
dcgm-exporter
ingestor
ollama
worker
alerter
prometheus
grafana
ollama-pull
```

Static structural checks (Python + pyyaml, since promtool is not in the
operator's local PATH on Windows):

```text
jobs:    ['ingestor', 'worker', 'alerter', 'dashboard', 'dcgm', 'prometheus']
alerts:  7
panels:  10
```

`promtool check config` and `promtool check rules` were not run in this
session because the host does not have the prometheus binary available; the
WP-7b operator will re-run them inside the running prometheus container once
the stack is up:

```bash
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
docker compose exec prometheus promtool check rules /etc/prometheus/alerts.yml
```

## Alert rules (overview)

| Group | Rules | What it catches |
|---|---|---|
| `pipeline-saturation` | 2 | Queue backing up past 2h, or chunks being dropped |
| `stations` | 1 | Any station silent for >15min |
| `worker-health` | 2 | Worker process up but stalled, or ASR RTF >1.0 |
| `gpu` | 2 | GPU temp >85°C sustained, or VRAM >92% |

Total: **7 firing-condition rules**. Alertmanager is intentionally absent
(WP-10a scope). The alerter service handles operational notifications via
Telegram directly (per PLAN §"Observability" — daily digest + ops alerts).

## Dashboard panels (overview)

| # | Type | Title |
|---|---|---|
| 1 | stat | Queue depth (pending hours) |
| 2 | timeseries | Chunks processed / hour (by service) |
| 3 | timeseries | Chunks dropped / 10m |
| 4 | timeseries | ASR real-time factor |
| 5 | timeseries | LLM extraction latency (p50 / p95) |
| 6 | timeseries | Detections / hour |
| 7 | timeseries | Station uptime (last chunk ago) |
| 8 | timeseries | GPU utilization (DCGM) |
| 9 | timeseries | GPU memory used (DCGM) |
| 10 | stat | Active alerts (firing count) |

Time range defaults to last 6h, refresh 30s.

## Out of scope (deferred)

- **Alertmanager** — the pipeline's "ops" alerts (station down, queue drop)
  go through the alerter service, not Alertmanager. If/when we add email
  or PagerDuty routing, this is where Alertmanager plugs in.
- **Ollama `/metrics`** — Ollama's metrics endpoint is uncommented in
  `prometheus.yml` but not enabled by default; will be turned on after
  WP-4 is shipping.
- **Recording rules** — long-term, complex aggregations will be precomputed
  for faster dashboard loads. Not needed at 4-10 stations.
- **TLS / auth on Prometheus** — bound to 127.0.0.1 only, like Grafana.

## Deviations

- `GRAFANA_ADMIN_PASSWORD` defaults to `admin` for dev. WP-7b (operator) must
  override this in `.env` before any non-localhost exposure.
- dcgm-exporter is given `cap_add: SYS_ADMIN` per its docs. Some hardened
  hosts may not allow this; if so, switch to a privileged mode override.

## Next

- WP-10b (this agent, M3, **deferred until ingestor + alerter exist**) —
  instrument every service with `prometheus_client.start_http_server` using
  the metric names + port numbers pinned in this report.
- WP-7b (operator, GPT mini) — live `docker compose up` + verify that
  prometheus, grafana, and dcgm-exporter come up healthy.
