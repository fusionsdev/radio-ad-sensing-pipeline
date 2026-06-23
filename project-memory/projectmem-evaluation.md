# projectmem Evaluation

## Status

**Initialized** — controlled init completed 2026-06-23 (RS-PMEM-001).

## Environment Check

- projectmem command available: **yes** — `.venv/Scripts/pjm` (`projectmem@0.1.5`)
- pjm init completed: **yes** — `pjm init --no-claude-md`
- `.projectmem` created: **yes** — events, summary, PROJECT_MAP, AI_INSTRUCTIONS, config.toml
- Git hooks installed: **yes** — pre-commit, post-commit (chained), post-merge
- Hook conflict: **resolved** — no prior active hooks; post-commit chained with Understand-Anything (see `projectmem-hook-policy.md`)
- MCP added: **yes** — `.cursor/mcp.json` (command from `pjm init` output)
- CLAUDE.md merged: **yes** — shim to `AGENTS.md` + priority order; init skipped CLAUDE.md overwrite

## Policy

- `project-memory/` remains human-readable source of truth (Obsidian vault + flat files).
- `LESSONS_LEARNED.md` remains mandatory mistake/prevention log.
- `.projectmem/` is machine event memory and warning layer (issues, attempts, fixes, decisions).
- `AGENTS.md` remains canonical agent contract — projectmem does not replace it.
- `.projectmem/events.jsonl` is **not** gitignored (committed per projectmem policy); only `watch.pid` / `watch.log` ignored.

## Layer map

| Layer | Role |
|---|---|
| Task Master (`.taskmaster/`) | What to do next |
| `AGENTS.md` | Rules |
| `project-memory/` | Durable human knowledge |
| `LESSONS_LEARNED.md` | Mistakes / prevention |
| `.projectmem/` | Event memory + pre-commit warnings |

## Follow-ups

- Restart Cursor after MCP change (cold start).
- Review `.projectmem/` diff before first commit (backfill added 16 events from git history).
- Optional: `pjm brief` at session start; populate PROJECT_MAP if agents enter Setup Mode.
- Do not re-run `pjm init` without `--no-claude-md` — would append bridge block to CLAUDE.md.

## MCP Status

MCP added from local `pjm init` printed config:

```json
"projectmem": {
  "command": "H:/DEV/projects/radio-ad-sensing-pipeline/.venv/Scripts/python.exe",
  "args": ["-m", "projectmem.mcp_server", "--root", "H:/DEV/projects/radio-ad-sensing-pipeline"]
}
```