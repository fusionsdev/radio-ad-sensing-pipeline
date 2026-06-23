# Agent Rules

These rules apply to Cursor, Codex, Claude Code, Hermes, Grok, and any other AI coding agent working on RadioSense.

Canonical contract: `AGENTS.md`. Shim index: `config/agent-memory-contract.md`.

## Before Changes

- Inspect repo state (`git status --short`).
- Read `AGENTS.md`.
- Read relevant `project-memory/*.md` (flat files + numbered vault entry points per `04_Agent_Load_Order.md`).
- Identify whether task affects runtime, dashboard, classifier, station control, or docs only.

## During Changes

- Keep changes small.
- Prefer additive docs/config/memory updates.
- Avoid unrelated refactors.
- Do not change live pipeline behavior unless explicitly requested.

## After Changes

- Run focused tests (`.venv\Scripts\pytest -q`).
- Run `python tools/harness/run_all.py` when behavior, policy, or memory docs may affect harness gates.
- Update memory files (vault loggers or flat index files).
- Report commands and results.
- Record mistakes in `LESSONS_LEARNED.md`.

## Required Final Report

```md
## Summary
## Files Changed
## Commands Run
## Test Results
## Memory Updated
## Risks / Follow-ups
```