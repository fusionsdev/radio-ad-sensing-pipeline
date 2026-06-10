# WP-7b Report — Docker Finalize

**Date:** 2026-06-10  
**Status:** Complete  
**Scope:** Compose finalization for Phase 7

## Scope

Validated and tightened the Docker Compose wiring without changing any business
logic:

- NVIDIA runtime usage stays limited to `worker`, `ollama`, and
  `dcgm-exporter`
- `ollama-pull` remains a one-shot init container that pulls the Qwen model
- Metrics ports `9101-9104` are exposed for `ingestor`, `worker`, `alerter`,
  and `dashboard`
- Restart policies, healthchecks, and volume mounts remain coherent
- Secrets stay runtime-only through compose environment interpolation

## Compose changes

| Item | Result |
|---|---|
| `ingestor` metrics | `expose: ["9101"]` |
| `worker` metrics | `expose: ["9102"]` |
| `alerter` metrics | `expose: ["9103"]` |
| `dashboard` metrics | `expose: ["9104"]` |
| Worker startup | Now waits for `ollama-pull` to complete successfully |
| NVIDIA runtime scope | Unchanged, still only `worker`, `ollama`, `dcgm-exporter` |
| Secrets handling | Still runtime env only; no `.env` values baked into images |

## Verification

```bash
docker compose config --quiet
```

Result: exit 0

## Notes

- `ollama-pull` still posts to `/api/pull` for `qwen2.5:7b-instruct-q4_K_M`.
- The metrics ports are exposed on the internal compose network only; they are
  not published to the host.
- I did not run a full `docker compose up` smoke test in this session.

## Manual verify steps

If the operator wants to complete the live bring-up, run:

```bash
docker compose up -d
docker compose ps
docker compose logs -f ollama ollama-pull worker
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
docker compose exec prometheus promtool check rules /etc/prometheus/alerts.yml
```

Then confirm:

- `ollama-pull` exits `0`
- `worker` starts after `ollama-pull`
- Prometheus can scrape `ingestor:9101`, `worker:9102`, `alerter:9103`, and
  `dashboard:9104`
- `dcgm-exporter` is reachable on `:9400` inside the compose network

## Next

WP-7b is ready for the operator's live GPU-host smoke test. No further compose
changes are required for this batch.
