# Decision

Date: 2026-06-23

## Context

Restored pytest to 465/465 and audited KLIF/WBAP last-24h candidates before station expansion.

## Decision

Do not add KTRH/WSB yet; KLIF/WBAP sample was 0/50 true consumer personal loan ads. Added cash advance to live scan config and bounded SSE once=true probe.

## Impact

TBD

## Rollback

Revert related files to prior commit.

## Related Files

- `plan/patch-e1-test-quality-audit-20260623.md`
- `config/vertical_keywords.yaml`
- `dashboard/routes/radiosense.py`
- `shared/keyword_hits_audit.py`