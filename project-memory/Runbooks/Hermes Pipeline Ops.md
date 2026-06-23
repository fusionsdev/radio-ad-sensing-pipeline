# Hermes Pipeline Ops

Trigger: `/pipeline-ops` in Hermes Telegram gateway.

## Rules

- Loan-only mode — consumer personal loans
- DB source: `/app/data/pipeline.db` inside `radio-worker`
- Stale if latest chunk >30 minutes — do not report keyword conclusions

## Response format

1. Action (`no_action`, `review_new_loan_candidate`, `rotate_station`, `fix_stream`, `pipeline_problem`, `source_stale_warning`)
2. DB freshness + latest chunk age
3. true_loan counts 1h / 6h / 24h (skip if stale)
4. Rotate/watch stations if any

## Skill reference

`.agents/skills/pipeline-ops/SKILL.md`

## Related

- [[02_Operating_Policy]]
- [[03_Forbidden_Assumptions]]