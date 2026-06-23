# RadioSense Project Memory

This folder is the durable memory layer for AI agents and human operators.

Use it to avoid rediscovering project structure, old incidents, station decisions, classifier rules, and dashboard behavior.

## Two layers (use both)

### Obsidian vault (canonical depth)

Numbered entry points and dated notes — preferred for decisions, incidents, and runbooks:

- `00_Project_Overview.md` — project scope and goals
- `01_Current_Architecture.md` — system structure
- `02_Operating_Policy.md` — ops policy
- `03_Forbidden_Assumptions.md` — what agents must not assume
- `04_Agent_Load_Order.md` — mandatory load order for all agents
- `Decisions/` — dated architecture/product decisions
- `Incidents/` — dated outage and bug records
- `Runbooks/` — operator procedures
- `Stations/` — station batch and rotation policy
- `Latest_Status.md` — session status snapshot

Optional enrichment: Obsidian MCP (`config/obsidian-mcp.json`), Smart Connections plugin.

### Quick-reference flat files (agent scaffold)

Shorter index files for fast agent lookup — point to vault notes when detail exists:

- `decisions.md` — product and architecture decisions
- `architecture.md` — current system structure summary
- `station-ops.md` — station keep/pause/rotate/probe rules
- `classifier-notes.md` — classifier logic, accepted patterns, exclusions
- `incidents.md` — incident index and template
- `agent-rules.md` — operational rules for Codex, Cursor, Claude, Hermes, Grok
- `daily-status-template.md` — format for recurring project status
- `projectmem-evaluation.md` — projectmem tool compatibility notes

## Repo-root companions

- `AGENTS.md` — canonical agent contract
- `LESSONS_LEARNED.md` — mistakes, failed assumptions, prevention
- `TASKS.md` — manual task tracking (Task Master fallback)
- `RUNBOOK.md` — safe debugging runbook