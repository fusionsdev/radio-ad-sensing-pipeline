# Operating Policy

## AI layer

| Use | Do not assume |
|---|---|
| Hermes local gateway | Gemini API |
| Ollama on-box (Qwen) | Claude API |
| Cursor agent (this repo) | OpenAI API |

Cloud APIs are valid only when explicitly configured in operator env — never default.

## Before every coding task

Load mandatory memory (in order):

1. `project-memory/00_Project_Overview.md`
2. `project-memory/01_Current_Architecture.md`
3. `project-memory/02_Operating_Policy.md`
4. `project-memory/03_Forbidden_Assumptions.md`
5. `project-memory/04_Agent_Load_Order.md`

Also read `AGENTS.md` and relevant `plan/handoff-*.md` when continuing work.

## After every coding task

```bash
.venv\Scripts\pytest -q
python tools/harness/run_all.py
```

Completion report must include: files changed, tests run, harness result, remaining risks, memory files updated.

## Database policy

| Context | Rule |
|---|---|
| Live ingest running | Query via `docker exec radio-worker` only |
| Harness / tests | Use `data/test.db` or pytest `tmp_path` — never `data/pipeline.db` |
| Host bind-mount | Stale during Docker ingest — do not trust for ops conclusions |

## Station policy

- Target vertical: **consumer personal loans**
- Rotation decisions: keep (≥2 unique loan advertisers), watch (1), rotate_out (0)
- Classifier: strict phrase-level — see `scripts/loan_classifier.py`
- Batch list: `.hermes.md` § `/pipeline-ops`

## Self-healing policy

- Harness **reports** unhealthy/exited containers — does **not** restart by default
- Restart only with explicit flag: `python tools/harness/run_all.py --execute-self-heal`
- Watchdog auto-restart is production behavior — harness stays read-only unless flagged

## Harness overnight readiness

`tools/harness/reports/latest.md` includes an overnight readiness verdict when all checks pass.

## Related notes

- [[03_Forbidden_Assumptions]]
- [[04_Agent_Load_Order]]
- [[Runbooks/Hermes Pipeline Ops]]