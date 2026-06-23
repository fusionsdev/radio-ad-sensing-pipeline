# Decision

Date: 2026-06-23

## Context

Need offline validation of exported KLIF/WBAP audio chunks against NVIDIA Parakeet/Riva without touching live ASR, classifier, station config, Docker services, or source audio.

## Decision

Add scripts/audit/parakeet_batch_transcribe.py as an audit-only CLI that reads NVIDIA_API_KEY from env, converts temporary 16kHz mono PCM, appends JSONL records, supports resume, and emits optional keyword_hits.

## Impact

TBD

## Rollback

Revert related files to prior commit.

## Related Files

- `scripts/audit/parakeet_batch_transcribe.py`
- `docs/PARAKEET_AUDIT_WORKFLOW.md`
- `tests/test_parakeet_batch_transcribe.py`