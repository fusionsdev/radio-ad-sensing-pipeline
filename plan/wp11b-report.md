# WP-11b Report — Extraction Eval Set

**Date:** 2026-06-10  
**Status:** Complete

## Scope

Implemented the Phase 11 extraction eval-set slice described in `PLAN.md`:

- added a fixture corpus of loan-ad-style transcripts under `tests/fixtures/extraction_eval/`
- documented ground truth in a JSON manifest for manual Ollama evaluation runs
- added CI-safe tests that score the fixtures through `normalize_phone_number` and a mock `OllamaExtractor`

## Deliverables

| Item | Location |
|---|---|
| Eval manifest + transcripts | `tests/fixtures/extraction_eval/` |
| Eval scorer test | `tests/test_extraction_eval.py` |
| Ground-truth fields | `expected.is_ad`, `expected.company_name`, `expected.phone` |

## Eval corpus

- 4 positive ads with CTA + offer + phone/contact language
- 3 negative non-commercial segments about loans, rates, or lending education
- mock extractor payloads included in the manifest-backed test flow so CI stays offline

## Scoring rubric

The test passes when each fixture satisfies all of the following:

- `is_ad` matches the ground truth exactly
- `company_name` matches loosely by normalized token subset, so suffix noise like `LLC` or `Co.` is tolerated
- `phone_number` is accepted if `normalize_phone_number(actual)` matches the manifest phone

This keeps the eval set useful both for deterministic CI and for later manual runs against a live Ollama model using the same transcripts and expected outcomes.

## Verification

```bash
.venv\Scripts\pytest tests/test_extraction_eval.py -v
.venv\Scripts\pytest -q
```

## Verification results

- `.venv\Scripts\pytest tests/test_extraction_eval.py -v` -> `3 passed`
- `.venv\Scripts\pytest -q` -> `82 passed, 1 failed`

The failing test was unrelated to WP-11b:

- `tests/test_db.py::test_concurrent_writes_retry_on_sqlite_busy`
- failure point: `assert saw_busy.wait(timeout=5)`
