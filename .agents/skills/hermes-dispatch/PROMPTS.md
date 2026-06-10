# Hermes Review Prompts

Copy the block matching your review type into `--prompt` or `-PromptFile`.

---

## WP gate (standard)

```
Act as independent review gate. Read the bundled input in order:
1. PLAN.md constraints (do not re-litigate architecture)
2. Implementer report claims
3. Changed files list

Review axes:
- Spec: every acceptance criterion — flag unverified claims
- Standards: shared/ import-light, short DB transactions, no secrets in code/logs

Output format:
## Findings (critical / major / minor)
- [severity] file:line — problem — suggested fix

## Verified commands
- what you trust vs what needs re-run

## Verdict
VERDICT: ship | fix-then-ship | rework
```

---

## WP-13 hardening (codexplan)

```
Review WP-13 Production Hardening per plan/codexplan.md.

Focus:
- WAL: checkpoint_wal(PASSIVE) in janitor; read-only connections skip journal_mode write
- Metrics: pipeline_sqlite_wal_* gauges update correctly
- docker-compose.prod.yml: pipeline_data named volume; chunk-tmpfs unchanged
- ASR: medium.en default unchanged; ASR_MODEL env override; asr_benchmark uses fake factory in CI

Do not ask to change fingerprint 0.88, Ollama temperature 0, or default ASR model.

Output findings by severity, then:
VERDICT: ship | fix-then-ship | rework
```

---

## Stream B only (Gemini — storage + ASR)

```
Review Gemini stream B for WP-13 only. Scope:
- docker-compose.prod.yml named volume pipeline_data
- shared/config.py ASR_MODEL / ASR_COMPUTE_TYPE env overrides
- worker/asr_benchmark.py CLI and tests with fake model factory

Do not review WAL/janitor/metrics (Cursor stream A).

VERDICT: ship | fix-then-ship | rework
```

---

## Stream A only (Cursor — WAL)

```
Review Cursor stream A for WP-13 only. Scope:
- shared/db.py WalCheckpointResult + checkpoint_wal(PASSIVE)
- read-only get_connection skips journal_mode WAL write
- worker/janitor.py passive checkpoint in run_sweep
- shared/metrics.py pipeline_sqlite_wal_* gauges

Do not review docker-compose.prod or asr_benchmark (Gemini stream B).

VERDICT: ship | fix-then-ship | rework
```

---

## Operator smoke reminder

```
Review whether operator-only smokes are documented (no code changes):
- docker compose -f docker-compose.yml -f docker-compose.prod.yml config
- GPU asr_benchmark on 5–10 min WAV sample
- live ingestor 5 min (WP-2 F6)

Report runbook gaps only.
VERDICT: ship | fix-then-ship | rework
```
