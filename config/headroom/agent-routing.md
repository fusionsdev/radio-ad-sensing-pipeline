# Headroom Agent Routing — RadioSense

## Supported agents

| Agent | Shim | Headroom |
|---|---|---|
| Cursor | `.cursor/rules/headroom-context.mdc` | Use when proxy up |
| Codex | `CODEX.md` | Use when proxy up |
| Claude Code | `CLAUDE.md` | Use when proxy up |
| Grok | `GROK.md` | Use when proxy up |
| Hermes | `.hermes.md` | Documented only — no runtime change in Phase 1.9 |

## Rules (all agents)

1. Read `AGENTS.md` first — Headroom does not replace canonical contract
2. Read `project-memory/04_Agent_Load_Order.md` before coding
3. Prefer compressed context; avoid loading unnecessary vault files
4. Run `python tools/harness/run_all.py` after behavior or policy changes
5. Do **not** use Headroom for classifier, station, ingestor, or DB decisions

## When Headroom is offline

Fall back to normal Memory OS load order. Harness reports WARNING on port `8787`.