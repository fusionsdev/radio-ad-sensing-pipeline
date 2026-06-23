# Decision

Date: 2026-06-23

## Context

Unify Memory OS across Cursor, Codex, Claude Code, Grok, Hermes

## Decision

AGENTS.md remains canonical; agent shims + config/agent-memory-contract.md + Cursor rule; Hermes preload vault on /pipeline-ops

## Impact

TBD

## Rollback

Revert related files to prior commit.

## Related Files

- `AGENTS.md`
- `CLAUDE.md`
- `GROK.md`
- `CODEX.md`
- `config/agent-memory-contract.md`
- `.cursor/rules/radiosense-memory.mdc`
- `.hermes.md`
- `.agents/skills/pipeline-ops/SKILL.md`
- `project-memory/04_Agent_Load_Order.md`
- `tools/harness/runners/hermes_harness.py`