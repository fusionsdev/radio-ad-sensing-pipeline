# Decision

Date: 2026-06-23

## Context

Integrate Headroom as context compression layer for multi-agent Memory OS without classifier/station/ingestor/DB changes.

## Decision

Add config/headroom/, agent shims, Cursor headroom rule, headroom_harness wired into run_all.py. Proxy optional (WARNING when offline). No zvec/RAG. Hermes runtime unchanged.

## Impact

TBD

## Rollback

Revert related files to prior commit.

## Related Files

- `config/headroom/README.md`
- `config/headroom/headroom-settings.md`
- `config/headroom/agent-routing.md`
- `config/headroom/integration-status.md`
- `.cursor/rules/headroom-context.mdc`
- `tools/harness/runners/headroom_harness.py`
- `CODEX.md`
- `CLAUDE.md`
- `GROK.md`