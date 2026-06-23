# CODEX.md — RadioSense

Codex must follow `AGENTS.md`.

## MCP Scope

When working in this repo, Codex may use only these RadioSense-specific MCP servers:

- `radiosense_projectmem`
- `radiosense_task_master`

Do not use generic or cross-project MCP memory for RadioSense decisions.

Do not use RadioSense MCP servers when working outside this repo.

## Instruction Priority

1. User instruction
2. `AGENTS.md`
3. `CODEX.md`
4. `project-memory/`
5. `LESSONS_LEARNED.md`
6. `.projectmem/AI_INSTRUCTIONS.md`

## Runtime Safety

Do not modify live ingestion, scheduler, worker count, DB schema, station runtime, Docker behavior, or classifier behavior unless explicitly requested.

Do not add MCP servers that can restart services, write to the production DB, change stations, or mutate live pipeline state.

## Oracle external review

For risky/complex reviews, load `project-memory/workflows/oracle-review-workflow.md`. MCP `oracle` is available; use short CLI commands unless troubleshooting.

## After coding

- run `python tools/harness/run_all.py`
- update project-memory if behavior changed
- append to `LESSONS_LEARNED.md` if a mistake or failed assumption occurred

Final reports must use the format defined in `AGENTS.md`.