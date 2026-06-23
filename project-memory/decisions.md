# RadioSense Decisions

Quick-reference index. Dated decisions live in `Decisions/` (Obsidian vault).

## Active Decisions

### Consumer personal loan only

RadioSense currently prioritizes consumer personal loan ads only.

Excluded categories:

- tax relief
- insurance
- identity protection
- general debt relief
- car dealer financing
- home improvement financing
- supplements
- unrelated local services

Reason:
The current affiliate/ad-testing target is consumer personal loans. Broad financial detections create poor signal and waste review time.

See also: `03_Forbidden_Assumptions.md`, `config/consumer_personal_loan_taxonomy.yaml`.

### Multi-agent memory contract

All agents (Cursor, Codex, Claude Code, Grok, Hermes) share `AGENTS.md` + `project-memory/`.

See: `Decisions/2026-06-23-multi-agent-memory-contract.md`, `config/agent-memory-contract.md`.

## Logging new decisions

```bash
python tools/memory/decision_logger.py "title" --context "…" --decision "…" --related-files <paths>
```