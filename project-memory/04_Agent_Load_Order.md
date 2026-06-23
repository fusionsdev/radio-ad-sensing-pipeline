# Agent Load Order

Every AI agent (Cursor, Hermes, Claude Code) **must** load these files before making code changes.

## Mandatory (always)

```txt
project-memory/00_Project_Overview.md
project-memory/01_Current_Architecture.md
project-memory/02_Operating_Policy.md
project-memory/03_Forbidden_Assumptions.md
project-memory/04_Agent_Load_Order.md   ← this file
```

## Session memory (repo root)

```txt
AGENTS.md
.hermes.md                    ← when doing pipeline ops
PLAN.md                       ← when changing architecture (do not re-litigate)
```

## Task-specific (load when relevant)

| Task | Also load |
|---|---|
| Pipeline ops | `.agents/skills/pipeline-ops/SKILL.md`, `docs/OPERATOR_WORKFLOW.md` |
| Station rotation | `scripts/loan_classifier.py`, `config/stations.yaml` |
| Dashboard API | `dashboard/routes/radiosense.py`, `dashboard/routes/harvest.py` |
| Watchdog | `watchdog/station_watchdog.py`, `config/settings.yaml` |
| Classifier / verticals | `config/consumer_personal_loan_taxonomy.yaml` |
| Continuing WP | Latest `plan/handoff-*.md` |

## MCP access (optional enrichment)

When Obsidian MCP is configured (`config/obsidian-mcp.json`):

- Search vault for runbooks, incidents, decisions
- Prefer vault runbooks over re-deriving ops steps from code

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