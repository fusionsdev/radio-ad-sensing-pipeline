# Grok Instructions

This project uses `AGENTS.md` as the canonical memory contract.

Before answering or coding:

- read `AGENTS.md`
- read `project-memory/04_Agent_Load_Order.md`
- load relevant memory files

Do not assume Gemini/cloud AI.
Do not broaden target beyond consumer personal loans.
Run harness after code changes.

For Oracle (ChatGPT) external review: `project-memory/workflows/oracle-review-workflow.md`

## API wrapper system prompt

If Grok is used via API wrapper, inject this as system prompt:

```txt
You are working on RadioSense.
Before coding, load AGENTS.md and project-memory/04_Agent_Load_Order.md.
Follow project-memory rules.
After coding, run python tools/harness/run_all.py.
If behavior changed, update project-memory.
```