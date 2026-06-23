# Task Master — RadioSense Setup

## Installed

- CLI: `task-master` (npm global `task-master-ai@0.43.1`)
- Project config: `.taskmaster/config.json`
- Tasks: `.taskmaster/tasks/tasks.json` (tag: `master`)

## Models (local Ollama)

This project uses on-box Ollama — **not** cloud API keys by default.

```bash
task-master models --set-main qwen3:8b --ollama
task-master models --set-research qwen3:8b --ollama
task-master models --set-fallback qwen3:8b --ollama
```

Verify Ollama is up:

```bash
curl http://127.0.0.1:11434/api/tags
```

## Common "stuck" causes

| Symptom | Cause | Fix |
|---|---|---|
| `task-master init` hangs | Interactive prompts | Use `task-master init -y --no-git --rules cursor` |
| `parse-prd` / `add-task --prompt` hangs | No API key / wrong provider | Set Ollama models (above) or add manual tasks with `--title` |
| MCP errors / timeout | Placeholder keys in mcp.json | Use `.cursor/mcp.json` with `OLLAMA_BASE_URL` only; restart Cursor |
| `ollama list` slow on Windows | CLI cold start | Use `curl http://127.0.0.1:11434/api/tags` instead |
| No tasks after init | `tasks.json` not created | Import manual tasks or run `parse-prd` after PRD exists |

## Daily commands

```bash
task-master list
task-master next
task-master show <id>
task-master set-status --id=<id> --status=done
```

Manual task (no AI):

```bash
task-master add-task --title "..." --description "..." --priority medium
```

## MCP (Cursor)

`.cursor/mcp.json` includes `task-master-ai` + `obsidian`. Restart Cursor after edits.

Do **not** let Task Master overwrite `AGENTS.md`, `project-memory/`, or runtime code.