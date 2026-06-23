# CLAUDE.md — RadioSense

Claude Code must follow `AGENTS.md`.

Also read `.projectmem/AI_INSTRUCTIONS.md` if present (projectmem event memory + workflow).

## Priority order

1. User instruction
2. `AGENTS.md`
3. `project-memory/` (Obsidian vault + flat index files)
4. `LESSONS_LEARNED.md`
5. `.projectmem/AI_INSTRUCTIONS.md` (machine event memory — do not replace vault docs)

## Headroom (context compression)

When Headroom proxy is available (`http://127.0.0.1:8787`):

- Prefer compressed context from Headroom
- Avoid loading unnecessary vault files
- Do not skip `AGENTS.md` or forbidden-assumptions policy

When proxy is offline: use normal Memory OS load order. Config: `config/headroom/`

## Before making changes

1. Read `AGENTS.md`.
2. Read relevant files under `project-memory/` (numbered vault files per `04_Agent_Load_Order.md` plus flat index files when useful).
3. Inspect `git status`.
4. Make the smallest safe change.
5. Run focused tests.
6. Update memory when the task changes decisions, incidents, classifier behavior, station ops, architecture, or runbooks.

Do not change live ingestion, scheduler, worker count, DB schema, or classifier behavior unless explicitly requested.

Use MCP Obsidian tools when available (`config/obsidian-mcp.json`).  
Use projectmem MCP for issue/attempt/fix logging when available.

For Oracle external review: `project-memory/workflows/oracle-review-workflow.md`

## After coding

- run `python tools/harness/run_all.py`
- update project-memory if behavior changed
- append to `LESSONS_LEARNED.md` if a mistake or failed assumption occurred
- log significant debug cycles via projectmem (`pjm` / MCP) when applicable

Final reports must use the format defined in `AGENTS.md`.