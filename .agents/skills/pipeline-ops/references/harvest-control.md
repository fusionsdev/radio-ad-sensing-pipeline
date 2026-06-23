# Harvest Control CLI — Safe Run Mode

Reference for `scripts/harvest_control.py` and `config/harvest_profiles.yaml`.
The CLI is a Safe Run Mode runner for overnight keyword harvest — probe
streams, start/stop a session, view status, export candidates, show top,
write a summary. It never edits source, migrates the DB, deploys, or runs
browser/trademark/compliance work.

## Commands (per-subcommand `--profile`, not global)

```
python scripts/harvest_control.py probe   [--limit N] [--profile overnight_keyword_harvest]
python scripts/harvest_control.py start   [--profile overnight_keyword_harvest]
python scripts/harvest_control.py stop
python scripts/harvest_control.py status
python scripts/harvest_control.py export  [--limit N] [--profile ...]
python scripts/harvest_control.py top     --limit N  [--profile ...]
python scripts/harvest_control.py summary [--profile ...]
```

`--profile` is a **per-subcommand** argparse arg (e.g. `start --profile X`),
NOT a global flag. The expected CLI form is `start --profile ...`, so the
parser adds `--profile` to each subparser, not to the root parser. The DB
override `--db` stays on the root parser.

## Output files

- `exports/overnight_keyword_candidates.csv`  (all candidates)
- `exports/overnight_keyword_candidates.jsonl`
- `exports/overnight_keyword_summary.md`      (markdown report)
- `runtime/harvest_status.json`               (last command, session state, export metadata)

CLI auto-creates `exports/` and `runtime/`. Tests redirect these via the
`HARVEST_EXPORT_DIR` / `HARVEST_RUNTIME_DIR` env vars (see SKILL.md).

## Keyword harvest strategy — broad net, not loan-only

The strict `config/loan_keywords.yaml` scanner rejects almost everything
(all 44 keyword_hits land in tax/insurance/timeshare verticals on this corpus).
The overnight profile uses a **broad money-problem detection net**:

- money_problem phrases: need cash, fast cash, quick cash, cash today,
  emergency cash, short on cash, behind on bills, unexpected bills, pay bills,
  bad/poor/less-than-perfect credit, etc.
- loan_product phrases: personal loan, installment loan, cash loan, online
  loan, emergency loan, bad credit loan.
- approval_funding phrases: same/next day funding, get approved, direct
  deposit, apply online, dot com, visit / go to / official website.
- rejected verticals (drop unless money signal present): tax relief, IRS,
  back taxes, insurance, Medicare, timeshare, mortgage refinance, solar,
  injury lawyer, home warranty.
- ambiguous debt/bills/credit language → save as `status=review`, never discard.

### Candidate gating rule (the core fix)

`gather_keyword_candidates` walks `detections` + `transcripts`. For each row
it gates brand/domain candidates so neutral advertisers (wine, mattresses,
gold, antivirus, real estate, B2B marketing) are dropped:

```
rejected_blob = is_rejected_evidence(evidence_blob)
if rejected_blob and not scan.has_signal:   continue   # rejected vertical, no money signal
if not scan.has_signal and not scan.ambiguous: continue  # neutral product, no money/debt language
```

Only candidates with a money-problem signal OR ambiguous debt language (or
approved trademark seeds) survive. Status is `ready` when a clear signal
fires, `review` for ambiguous-only.

## Candidate sources (union, deduped)

1. `trademark_keyword_candidates` (seeds) → `source=trademark_seed`, the bulk.
2. `detections` + joined `transcripts` → `source=detection` (brand/domain +
   phrase candidates).
3. `keyword_hits` (broad net) → `source=keyword_hit`.
4. `advertiser_entities` (if populated) — note this table exists, NOT
   `advertiser_opportunities` despite migration 006's filename.

## DB schema facts (verified 2026-06-19)

- `trademark_keyword_candidates.trademark_entity_id` is **NOT NULL** with FK
  to `trademark_entities(id)`. Tests must insert a parent entity row first.
- `trademark_entities` columns: `canonical_name, normalized_name, source_type,
  review_status, trademark_risk, ad_copy_allowed, landing_page_allowed,
  reason, notes, cfpb_company_entity_id, created_at, updated_at`. There is
  NO `vertical`, `domain`, `confidence`, or `status` column — use
  `review_status` / `trademark_risk`.
- `trademark_keyword_candidates` columns: `id, trademark_entity_id, keyword,
  normalized_keyword, variant_type, source_type, status, ad_copy_allowed,
  confidence, score, created_at`. `score` is 0–100, `confidence` is 0–1.
  Normalize: `confidence = score/100 if score > 1.5 else confidence`.
- The actual table is `advertiser_entities`, not `advertiser_opportunities`
  (migration `006_advertiser_opportunities.sql` is misleadingly named).

## Test seeding pattern

When seeding `trademark_keyword_candidates` in tests, insert the parent first:

```python
INSERT INTO trademark_entities
    (canonical_name, normalized_name, source_type, review_status, trademark_risk, ad_copy_allowed)
VALUES ('CashSpot', 'cashspot', 'cfpb_complaint', 'approved', 'low', 1);

INSERT INTO trademark_keyword_candidates
    (trademark_entity_id, keyword, normalized_keyword, variant_type, source_type, status, confidence, score, created_at)
VALUES (1, 'CashSpot', 'cashspot', 'brand', 'cfpb_complaint', 'approved_seed', 1.0, 100.0, '2026-06-19T00:00:00Z');
```

## Python pitfall: closure-variable shadowing

`is_rejected_evidence(text)` references a module-level `rejected` set via
closure. Do NOT name a local variable `rejected` (a bool) in the enclosing
function that calls it — Python will shadow the closure and raise
`TypeError: 'bool' object is not iterable` from inside the helper. Rename the
local (e.g. `rejected_blob`). Generic Python gotcha but easy to hit when
filtering loops read "is this row rejected?".
