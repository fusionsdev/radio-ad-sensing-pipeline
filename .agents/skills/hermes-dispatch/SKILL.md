---
name: hermes-dispatch
description: >-
  Dispatch review tasks to Hermes agent via `hermes run` CLI — periodic WP gate,
  diff audit, plan compliance. Use when user says "hermes review", "ส่ง hermes",
  "hermes dispatch", or after closing a work package / before merge.
argument-hint: "[scope] e.g. wp13 or plan/codexplan.md"
---

# Hermes Dispatch — Periodic Review Gate

Send artifacts to Hermes agent for independent verification. Hermes **reviews only** — it does not implement fixes.

## When to run

| Trigger | Input | Output |
|---------|-------|--------|
| WP closed | `plan/wpN-report.md` + changed files | `plan/hermes-review-<scope>-<timestamp>.md` |
| Pre-merge hardening | `plan/codexplan.md` + diff stat | `plan/hermes-review-hardening-<timestamp>.md` |
| Post-pytest regression | saved pytest output | `plan/hermes-review-tests-<timestamp>.md` |
| Ad-hoc audit | single file or directory | user `--output` path |

## Prerequisites

- `hermes` CLI on PATH (`hermes --version` or `where hermes`)
- Hermes agent installed locally (Windows: `%LOCALAPPDATA%\hermes\`)
- Never pass `.env`, tokens, or secrets as `--input`

## Workflow

1. **Identify scope** — from user arg or conversation: WP id, plan path, or file path.
2. **Build review bundle** — write temp file `plan/_hermes-bundle-<scope>-<timestamp>.md` (gitignored):
   - Relevant `PLAN.md` section or path reference
   - Implementer report (`plan/wp*-report.md`) if it exists
   - Changed files: `git diff --name-only` (recent commits or branch vs main)
   - Latest `pytest -q` summary (run if not already done)
3. **Pick prompt** from `PROMPTS.md` matching review type.
4. **Run Hermes** (Windows — Hermes Agent CLI):

   ```powershell
   # Bundled script (recommended):
   .\.agents\skills\hermes-dispatch\scripts\hermes-review.ps1 `
     -Scope wp13 -PlanPath plan/codexplan.md -ReportPath plan/wp13-hardening-report.md

   # Manual one-shot (reads bundle into prompt):
   hermes -z "<prompt + bundle content>" --yolo --accept-hooks > plan/hermes-review-wp13.md
   ```

   Note: this project's Hermes install uses `hermes -z` / `hermes chat -Q -q`, not `hermes run`.

5. **Parse verdict** — report must end with one of:
   - `VERDICT: ship`
   - `VERDICT: fix-then-ship` (numbered fixes with file:line)
   - `VERDICT: rework`
6. **Act on verdict**:
   - `ship` → note in WP report or `AGENTS.md`
   - `fix-then-ship` → implement fixes in Cursor, re-dispatch Hermes on same scope
   - `rework` → escalate to human; do not merge
7. **Delete** temp bundle after successful run (optional keep for audit trail).

## Review axes (always both)

1. **Spec** — matches `PLAN.md` + handoff + implementer report?
2. **Standards** — `shared/` import-light, SQLite WAL patterns, no secrets in logs?

## Parallel implement + Hermes gate

| Role | Tool | Work |
|------|------|------|
| Implement B | Gemini CLI | e.g. compose.prod + ASR benchmark |
| Implement A | Cursor | e.g. WAL + janitor + metrics |
| Review gate | Hermes | after each stream merges; final gate after full WP |

## Do NOT

- Ask Hermes to implement code changes
- Send full repo, `data/` volumes, or secrets
- Trust implementer reports without listing unverified claims

## Periodic automation

Schedule via Windows Task Scheduler or `/loop`:

```powershell
.\.agents\skills\hermes-dispatch\scripts\hermes-review.ps1 -Scope nightly -PlanPath plan/codexplan.md
```

Not in CI by default (requires local Hermes + optional GPU smoke).

## Output location

All reports → `plan/hermes-review-*.md` (timestamp suffix; do not overwrite prior reviews).
