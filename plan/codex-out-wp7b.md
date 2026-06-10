Updated [docker-compose.yml](h:\DEV\projects\radio-ad-sensing-pipeline\docker-compose.yml) to:

- expose metrics ports internally for `ingestor:9101`, `worker:9102`, `alerter:9103`, and `dashboard:9104`
- keep NVIDIA runtime reservations limited to `worker`, `ollama`, and `dcgm-exporter`
- make `worker` wait for `ollama-pull` to finish so the Qwen pull is actually in place before the worker comes up

Wrote the handoff report at [plan/wp7b-report.md](h:\DEV\projects\radio-ad-sensing-pipeline\plan\wp7b-report.md), including the manual live-up verification steps for the GPU host.

Verification passed:

- `docker compose config --quiet`

If you want, the next practical step is a live `docker compose up -d` smoke test on the NVIDIA host.