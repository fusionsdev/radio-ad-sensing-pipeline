# WP-4 Report — LLM Extraction (Phase 4 fix-then-ship)

**Date:** 2026-06-10 (Batch 2 Session — Opus review fixes)  
**Status:** Complete (N1–N4)

## Scope

Opus Deep review (`plan/opus-review-plan-6165b3.md`) returned **fix-then-ship** for phone normalization edge cases and few-shot prompt quality. Core schema, retry-on-invalid-JSON, and metadata exclusion were already OK.

## Fixes applied

| ID | Issue | Fix |
|---|---|---|
| **N1** | Word-only spelled input fell through to T9 vanity on entire prose (`"one eight hundred tax help"` → garbage) | `normalize_phone_number` only calls `_parse_digits_and_vanity` when `_has_explicit_digits_or_vanity(raw)` (contains digits or digit+letter vanity like `1-800-CASH-NOW`) |
| **N2** | 7-digit minimum rejected valid toll-free prefix sequences | `_accept_spelled_digits` accepts shorter sequences when `_toll_free_prefix` matches 800/888/877/866/855/844/833 (with optional leading `1`) |
| **N3** | Missing regression tests | Added tests for partial spelled phones, prose-only rejection, few-shot ex.3, senator/loan-talk `is_ad=false` mock |
| **N4** | Few-shot example 3 showed raw spelled phone in JSON | Example now uses normalized `"8008294357"` (1-800-TAX-HELP) |

## Key behavior changes

- `"one eight hundred tax help"` → `"1800"` (toll-free prefix subsequence), not T9 garbage
- `"eight hundred"` → `"800"`
- `"eight hundred five five five"` → `"800555"`
- `"call us about loans today"` → `None` (no vanity fallback on prose)
- Digit/vanity paths unchanged: `"1-800-CASH-NOW"`, `"(212) 555-0199"`, full spelled `"eight hundred five five five one two one two"`

## Deliverables

| Item | Location |
|---|---|
| Ollama client + JSON schema + retry | `worker/extract.py` |
| Phone normalization (spelled + vanity + toll-free relax) | `worker/extract.py` |
| Extraction prompt + few-shot examples | `worker/extract.py` → `build_extraction_prompt` |
| Tests | `tests/test_extract.py` (8 tests) |

## Test results

```
.venv\Scripts\pytest tests/test_extract.py -v   → 8 passed
.venv\Scripts\pytest -q                         → 67 passed
```

New tests:

- `test_normalize_phone_number_rejects_word_only_vanity_garbage`
- `test_prompt_few_shot_example_three_uses_normalized_phone`
- `test_ollama_extractor_classifies_senator_loan_talk_as_non_ad`

## Verification

```bash
.venv\Scripts\pytest tests/test_extract.py -v
.venv\Scripts\pytest -q
```

## Deviations

None.
