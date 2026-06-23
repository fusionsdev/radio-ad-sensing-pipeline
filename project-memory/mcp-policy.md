# MCP Policy — RadioSense

## Policy

RadioSense-specific MCP servers should be project-scoped whenever possible.

If Codex Desktop only supports global MCP config, RadioSense MCP servers must use explicit `radiosense_` prefixes.

## Approved Codex MCP Servers

- `radiosense_projectmem` — event memory and warning layer
- `radiosense_task_master` — task planning and dependency tracking

## Not Approved Yet

- Obsidian MCP (Codex global — deferred this pass)
- station control MCP
- DB write MCP
- Docker control MCP
- dashboard restart MCP
- scheduler mutation MCP

## Reason

RadioSense has live runtime, station control, classifier logic, DB state, and watchdog behavior. MCP servers with write or runtime control can cause unintended production changes.

## Global Config Rule

Generic MCP servers may live in global Codex config.

Project-specific MCP servers must be prefixed by project name:

- good: `radiosense_projectmem`
- good: `radiosense_task_master`
- bad: `projectmem`
- bad: `task-master-ai`
- bad: `obsidian`

## Current Codex Config Location

Expected path:

`C:\Users\Barbara\.codex\config.toml`

Always verify the actual path before editing.

## Cursor (per-project)

Cursor uses `.cursor/mcp.json` with unprefixed names (`projectmem`, `task-master-ai`, `obsidian`) — scoped to this repo only when the project is open.