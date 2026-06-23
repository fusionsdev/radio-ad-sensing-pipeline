# RadioSense Multi-Agent Memory Contract

**Canonical source of truth:** `AGENTS.md`

All coding agents share the same Memory OS. Agent-specific files are **shims only** — they point back to `AGENTS.md` and `project-memory/04_Agent_Load_Order.md` without duplicating full policy.

## Shared contract

Every agent must use:

```txt
AGENTS.md
project-memory/
tools/harness/
```

## Mandatory load order

Before coding, load:

```txt
project-memory/00_Project_Overview.md
project-memory/01_Current_Architecture.md
project-memory/02_Operating_Policy.md
project-memory/03_Forbidden_Assumptions.md
project-memory/04_Agent_Load_Order.md
```

Optional enrichment: Obsidian MCP (`config/obsidian-mcp.json`).

## After coding

```bash
python tools/harness/run_all.py
```

Update project-memory when behavior, policy, station state, classifier logic, or architecture changes. See `AGENTS.md` § Required memory updates.

## Agent shims

| Agent | Entry file | Notes |
|---|---|---|
| **Cursor** | `.cursor/rules/radiosense-memory.mdc` | Session start + harness + scope guardrails |
| **Codex** | `CODEX.md` | Points to `AGENTS.md` |
| **Claude Code** | `CLAUDE.md` | Points to `AGENTS.md`; use Obsidian MCP when available |
| **Grok** | `GROK.md` | Points to `AGENTS.md`; API wrapper system prompt in file |
| **Hermes** | `.hermes.md` | Preloads vault on `/pipeline-ops`; skill: `.agents/skills/pipeline-ops/SKILL.md` |
| **Oracle** | `project-memory/workflows/oracle-review-workflow.md` | External ChatGPT review via `@steipete/oracle`; MCP `oracle` in Codex + Cursor |

## Forbidden assumptions (all agents)

- Do not assume Gemini / Claude API / OpenAI API unless explicitly configured (Oracle browser mode is OK for external review)
- Hermes local + Ollama on-box is the default AI layer
- Do not broaden target beyond consumer personal loans
- Do not read `data/pipeline.db` from Windows host during Docker ingest — use `docker exec radio-worker`

## Related

- `AGENTS.md`
- `project-memory/04_Agent_Load_Order.md`
- `docs/agent-tooling.md`
- `project-memory/workflows/oracle-review-workflow.md`