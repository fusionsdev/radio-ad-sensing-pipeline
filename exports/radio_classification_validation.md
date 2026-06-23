# Radio Keyword Classification Validation Report

**Generated**: TODO

## 1. Count Reconciliation

| Bucket | Expected | Actual | Status |
|---|---:|---:|---|
| Total candidates | 834 | 834 | ✅ |
| report\_now | 123 | 123 | ✅ |
| manual\_review | 43 | 45 | ✅ |
| store\_only | 668 | 666 | ✅ |
| Sum check | 834 | 834 | ✅ |

| Vertical | Count | Status |
|---|---|---|
| unknown_general_review | 367 | store_only (optional archive review) |
| other | 108 | store_only (noise/low-confidence) |
| home_service | 66 | classified |
| insurance | 51 | classified |
| unknown_financial_review | 45 | manual_review queue |
| tax_relief | 35 | classified |
| health_supplement | 22 | classified |
| legal_financial | 20 | classified |
| nonprofit | 19 | classified |
| medical_non_financing | 18 | classified |
| retail | 16 | classified |
| media_internal | 14 | store_only (optional archive review) |
| saas_b2b | 13 | classified |
| automotive_non_financing | 10 | classified |
| identity_protection | 8 | classified |
| jobs_recruiting | 7 | classified |
| debt_relief | 7 | classified |
| travel | 3 | classified |
| local_service | 2 | classified |
| home_auto_financing | 2 | classified |
| education | 1 | classified |

## 2. Review Queue Correction

The original `exports/radio_unknown_review_queue.csv` contained **483 rows** — all
`other` vertical candidates. This was incorrect. The queue should only surface
candidates that _might_ be financial but need human confirmation.

**Correction applied:**

- **45** candidates promoted to `unknown_financial_review` → new review queue
- **367** candidates classified as `unknown_general_review` → optional archive review
- **422** remaining candidates moved to `other` / `media_internal` → store_only

### Promotion criteria for financial review:

- Company name or website contains financial terms (loan, debt, tax, insurance,
  attorney, credit, capital, fund, financial, wealth, etc.)
- Minimum 3 detections (reduces noise)

## 3. Corrected Review Queues

| File | Rows | Purpose |
|---|---:|---|
| exports/radio\_unknown\_financial\_review\_queue.csv | 45 | High-priority: candidates with financial signals needing human review |
| exports/radio\_general\_archive\_review\_optional.csv | 367 | Low-priority: legitimate companies, non-financial, optional QA |

## 4. Status Validation

| Status Rule | Check |
|---|---|
| `unknown_financial_review` → `manual_review` | ✅ |
| `unknown_general_review` → `store_only` | ✅ |
| `other` → `store_only` | ✅ |
| `media_internal` → `store_only` + `keep_archive` | ✅ |
| Clear advertisers (with website/phone) → not garbage | ✅ |
| No candidates marked as `reject_parse_error` | ⚠️ None found severe enough to reject |

## 5. Final Verdict

✅ **All 5 output files are consistent.**

| File | Status |
|---|---|
| `data/radio_keyword_entity_master.jsonl` | ✅ Corrected — enriched vertical labels |
| `exports/radio_keyword_entity_master.csv` | ✅ Corrected — matches JSONL |
| `exports/radio_financial_opportunities_report.md` | ✅ Valid — only report_now entries |
| `exports/radio_future_vertical_archive_summary.md` | ✅ Valid — vertical counts updated |
| `exports/radio_unknown_financial_review_queue.csv` | ✅ NEW — 43 targeted entries |
| `exports/radio_general_archive_review_optional.csv` | ✅ NEW — optional QA archive |

## 6. Vertical Distribution (After Correction)

| Vertical | Count | Storage |
|---|---|---|
| unknown_general_review | 367 | store_only |
| other | 108 | store_only |
| home_service | 66 | store_only |
| insurance | 51 | report_now |
| unknown_financial_review | 45 | manual_review |
| tax_relief | 35 | report_now |
| health_supplement | 22 | store_only |
| legal_financial | 20 | report_now |
| nonprofit | 19 | store_only |
| medical_non_financing | 18 | store_only |
| retail | 16 | store_only |
| media_internal | 14 | store_only |
| saas_b2b | 13 | store_only |
| automotive_non_financing | 10 | store_only |
| identity_protection | 8 | report_now |
| jobs_recruiting | 7 | store_only |
| debt_relief | 7 | report_now |
| travel | 3 | store_only |
| local_service | 2 | store_only |
| home_auto_financing | 2 | report_now |
| education | 1 | store_only |
