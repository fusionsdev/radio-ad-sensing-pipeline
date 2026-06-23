# Agent Load Order

Every AI agent (**Cursor, Codex, Claude Code, Grok, Hermes**) **must** load these files before making code changes.

Canonical contract: `AGENTS.md` · Shim index: `config/agent-memory-contract.md`

## Mandatory (always)

```txt
AGENTS.md                     ← canonical source of truth (all agents)
project-memory/workflows/git-safety-workflow.md ← mandatory Git / branch / stash / PR / Linear safety gate
project-memory/workflows/linear-oracle-agent-workflow.md ← mandatory Linear / Oracle / Agent workflow
project-memory/00_Project_Overview.md
project-memory/01_Current_Architecture.md
project-memory/02_Operating_Policy.md
project-memory/03_Forbidden_Assumptions.md
project-memory/04_Agent_Load_Order.md   ← this file
```

## Session memory (repo root)

```txt
AGENTS.md                     ← canonical source of truth (all agents)
LESSONS_LEARNED.md            ← agent mistakes and failed assumptions
TASKS.md                      ← manual task fallback (Task Master unavailable)
RUNBOOK.md                    ← safe debugging runbook
CODEX.md / CLAUDE.md / GROK.md ← agent shims (point to AGENTS.md)
.cursor/rules/radiosense-memory.mdc      ← Cursor Memory OS
.cursor/rules/radiosense-agent-rules.mdc ← Cursor scope guardrails
.hermes.md                    ← Hermes /pipeline-ops
PLAN.md                       ← when changing architecture (do not re-litigate)
```

## Quick-reference flat files (optional, under project-memory/)

```txt
README.md
decisions.md
architecture.md
station-ops.md
classifier-notes.md
incidents.md
agent-rules.md
daily-status-template.md
projectmem-evaluation.md
workflows/oracle-review-workflow.md
```

## Task-specific (load when relevant)

| Task | Also load |
|---|---|
| Pipeline ops | `.agents/skills/pipeline-ops/SKILL.md`, `docs/OPERATOR_WORKFLOW.md` |
| Station rotation | `scripts/loan_classifier.py`, `config/stations.yaml` |
| Dashboard API | `dashboard/routes/radiosense.py`, `dashboard/routes/harvest.py` |
| Memory Dashboard UI | `H:\DEV\github_sandbox\radiosense-aistudio`, [[Runbooks/Memory Dashboard]] |
| Memory API / vault | `dashboard/routes/memory.py`, `tools/memory/vault_reader.py`, [[Runbooks/Memory Dashboard]] |
| Watchdog | `watchdog/station_watchdog.py`, `config/settings.yaml` |
| Classifier / verticals | `config/consumer_personal_loan_taxonomy.yaml` |
| Continuing WP | Latest `plan/handoff-*.md` |
| Git safety / repo state | `project-memory/workflows/git-safety-workflow.md` |
| Linear / Oracle workflow | `project-memory/workflows/linear-oracle-agent-workflow.md` |
| Oracle external review | `project-memory/workflows/oracle-review-workflow.md`, `~/.agents/skills/oracle/SKILL.md` |

## Obsidian enrichment (optional)

| Tool | Use |
|---|---|
| **Smart Connections** | Semantic lookup + related notes while editing memory |
| **obsidian-mcp-server** | Agent search/read vault via MCP (`config/obsidian-mcp.json`) |

Prefer vault runbooks over re-deriving ops steps from code.

Vault path: `project-memory/` (this directory).

## After coding (mandatory)

```bash
.venv\Scripts\pytest -q
python tools/harness/run_all.py
```

## Completion report template

```markdown
## Files changed
- ...

## Tests run
- pytest: N passed

## Harness result
- status: pass|fail
- report: tools/harness/reports/latest.md

## Remaining risks
- ...

## Memory files updated
- project-memory/... (or none)
```

## Related notes

- [[02_Operating_Policy]]
- [[00_Project_Overview]]
