# Classifier Notes

Quick-reference for consumer personal loan detection. Code: `worker/keywords.py`, `scripts/loan_classifier.py`, `config/consumer_personal_loan_taxonomy.yaml`.

## Target

Consumer personal loan only.

## Accepted Intent

Examples:

- personal loan
- installment loan
- emergency loan
- borrow money
- fast cash
- loan approval
- online loan offer
- cash loan

## Exclusions

Reject unless there is clear consumer personal loan intent:

- tax relief
- back taxes
- IRS
- insurance
- identity protection
- car dealer financing
- home windows
- roofing
- supplements
- medical ads
- generic bank branding
- credit repair without loan offer
- debt settlement without loan offer

## Change Rule

Classifier changes require:

1. New/updated tests.
2. Before/after detection count.
3. False-positive examples.
4. Clear explanation of new allowed and rejected phrases.
5. Update this file and run `python tools/harness/run_all.py` (decision harness enforces documentation).

See: `LESSONS_LEARNED.md` § Classifier broad keywords created false positives.