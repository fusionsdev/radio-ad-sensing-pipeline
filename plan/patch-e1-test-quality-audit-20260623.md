# Patch E.1 Follow-up: Test Recovery and 2-Station Quality Audit

Date: 2026-06-23

## Scope

- Restored the repo pytest suite after `watchdog-fixed-harvest-e1-pass`.
- Audited last-24h KLIF/WBAP evidence before any station expansion.
- Preserved fixed-harvest observe-only posture: watchdog should monitor/write manual attention only, not auto-disable or auto-promote.

## Test Recovery

Initial handoff said 100/101 passed, but current collection is 465 tests.

Findings fixed:

- `tests/test_apify_name_collector.py::test_load_queries` had stale expected count `150`; current `config/justia_name_queries.txt` contains 1200 active queries.
- Justia serial/slug parsers failed normal URLs like `https://trademarks.justia.com/872/36/loan-command-87236459.html`.
- `shared.keyword_hits_audit` incorrectly flagged exact consumer-loan target phrases as polluted solely because legacy `vertical_keywords.yaml` maps them under `loan`.
- `tests/test_config.py` expected stale ASR compute type `int8_float16`; committed config uses `float16`.
- Live scan config omitted `cash advance`, so accepted consumer-loan cash advance transcripts could not persist keyword hits.
- Harvest dashboard test expected an obsolete `/radio-harvest` self-link.
- `/api/live/events` SSE test hung on the infinite stream; route now supports `?once=true` for bounded probes while default remains streaming.
- USPTO verifier had the same Justia filename serial parsing bug and a case-sensitive dry-run assertion.

Verification:

- `.venv\Scripts\pytest -q` -> 465 passed, 1 warning.
- `python tools\harness\run_all.py` -> pass; overnight readiness ready.
- `python -c "from shared.db import migrate; migrate('data/test.db')"` -> pass.

## 2-Station Quality Audit

Live DB read path: Docker-side read-only query via `radio-ad-pipeline-worker-1:/app/data/pipeline.db`.

Last 24h volume:

| Station | Chunks | Transcripts | Keyword hits | Detections |
|---|---:|---:|---:|---:|
| KLIF AM 570 | 483 | 340 | 8 | 56 |
| WBAP AM 820 | 522 | 415 | 24 | 74 |

Exports:

- `exports/klif_wbap_last24h_transcripts_20260623.csv` — 752 rows
- `exports/klif_wbap_last24h_detections_20260623.csv` — 129 rows
- `exports/klif_wbap_quality_audit_candidates_20260623.csv` — 50 sampled candidate rows
- `exports/klif_wbap_quality_audit_labeled_20260623.csv` — 50 labeled rows

Manual labels:

| Label | Count |
|---|---:|
| true_loan_ad | 0 |
| false_positive | 50 |
| unclear | 0 |

By station:

| Station | false_positive | true_loan_ad | unclear |
|---|---:|---:|---:|
| KLIF AM 570 | 17 | 0 | 0 |
| WBAP AM 820 | 33 | 0 | 0 |

Dominant false-positive categories:

- tax relief: 22
- insurance: 9
- debt/timeshare relief: 5
- blank/general detections: 4
- other non-loan ads: weight loss, travel, health, pain relief, trucking insurance

## Station Expansion Decision

Do not add KTRH or WSB yet.

Reason: KLIF/WBAP are ingesting and producing transcripts, but the sampled candidate quality is 0/50 true consumer personal loan ads. Adding stations now would likely multiply noise before classifier/audit quality improves.

Recommended next step:

1. Clean legacy/non-target keyword-hit pollution from candidate selection.
2. Re-run KLIF/WBAP quality audit after the live scanner has more post-fix `cash advance` coverage.
3. Only then probe KTRH/WSB, add disabled, enable one at a time, and observe ingest/chunk/drop rate for 30-60 minutes.

## Oracle Review

Session: `review-patch-e-1-follow`

Oracle agreed:

- Keep station expansion blocked after a 0/50 true-loan audit.
- `cash advance` scan config is conditionally safe for persistence because classifier gating rejects generic, credit-card, and merchant cash-advance contexts.
- `/api/live/events?once=true` is safe because it preserves default streaming behavior and gives tests/health probes a bounded read.

Oracle risks / follow-ups:

- Candidate/audit surfaces are still polluted by legacy vertical rows unless exports filter through consumer-loan intent or old `keyword_hits` are cleaned.
- Add cleanup/export tests proving tax, insurance, debt/timeshare, supplements, and other excluded verticals do not appear in consumer-loan audit candidates.
- Add a historical cleanup test where `cash advance` context is credit-card/merchant/generic and should not pollute candidate sampling.
- Watchdog fixed-harvest behavior was not attached in this Oracle bundle; rely on local watchdog tests for E.1 verification or run a dedicated watchdog Oracle review if needed.
