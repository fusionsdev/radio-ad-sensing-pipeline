# RUNBOOK.md — RadioSense

Safe operational references for agents and operators. Does not replace `project-memory/Runbooks/` or `docs/OPERATOR_WORKFLOW.md`.

## Before Debugging

```bash
git status --short
docker compose ps
```

During Docker ingest, query live DB inside the worker container — not `data/pipeline.db` on the Windows host.

## Dashboard/API Mismatch

If dashboard behavior does not match source code:

1. Check container age (`docker compose ps`, image build time).
2. Check dashboard logs (`docker compose logs dashboard --tail 50`).
3. Rebuild dashboard container if needed (see `project-memory/Runbooks/Memory Dashboard.md`).
4. Verify route registration before changing code.

Recorded lesson: `LESSONS_LEARNED.md` § Dashboard container can serve stale code.

## Station Health Debugging

Check:

- valid chunks
- dropped chunks
- ffmpeg decode errors
- last successful chunk
- zero-transcript rate
- classifier yield

Do not change worker count until station health is audited.

Station policy: `project-memory/station-ops.md`, `project-memory/Stations/Batch Policy.md`.

## Classifier Debugging

For consumer personal loan classifier:

1. Collect examples.
2. Separate true positives and false positives.
3. Add tests.
4. Run before/after count.
5. Update `project-memory/classifier-notes.md`.

Taxonomy: `config/consumer_personal_loan_taxonomy.yaml`.

## Agent Session Closeout

```bash
.venv\Scripts\pytest -q
python tools/harness/run_all.py
```

## Required Final Report

```md
## Summary
## Files Changed
## Commands Run
## Test Results
## Memory Updated
## Risks / Follow-ups
```