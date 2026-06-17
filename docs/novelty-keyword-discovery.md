# Novelty-First Keyword Discovery

## Purpose

The novelty engine discovers **new** advertiser-intelligence opportunities without re-reporting common brands, generic finance keywords, or excluded verticals. It is an independent layer: it does not run inside the radio transcription worker.

**Core rule:** Known = dashboard only. Generic = dashboard only. Excluded = dashboard only. **New + relevant + evidence-backed = report eligible.**

## What counts as new

Report-eligible candidates are specific, novel phrases such as:

- Unknown brands or local/regional advertisers
- New use-case keywords (e.g. `dog ACL surgery payment plan`)
- Consumer pain phrases and ad-copy angles
- Competitor/alternative opportunities
- New domains or landing-page angles

## What gets suppressed

| Status | Meaning | Reported? |
|--------|---------|-----------|
| `known_duplicate` | Exact match to a known brand | No |
| `near_duplicate` | Fuzzy match ≥85% to known brand/keyword | No |
| `generic` | Known generic keyword (e.g. `pet financing`) | No |
| `excluded_vertical` | Vertical on exclusion list (e.g. `title_loan`) | No |
| `weak_evidence` | Missing required evidence text or source URL | No |
| `noise` | Empty or unusable text | No |
| `needs_review` | Novel but below score thresholds | No (dashboard) |
| `new` | Passes all gates | Yes, if scores meet thresholds |

## Known list behavior

- **`config/known_entities.yaml`** — national/service brands grouped by vertical family. Stored for matching; never reported as new opportunities when `reporting.report_known_brands: false`.
- **`config/known_keywords.yaml`** — generic finance phrases. Visible in dashboard under **Known / generic**; not reported when `reporting.report_known_keywords: false`.

## Excluded vertical behavior

- **`config/excluded_verticals.yaml`** — verticals stored for audit but never reported (`reporting.report_excluded_verticals: false`).
- Suppression applies when the candidate `vertical` field matches an excluded id **or** the normalized text equals an excluded slug.

## Thresholds

Configured in **`config/novelty_rules.yaml`**:

- `report_novelty_score` (default 75)
- `report_opportunity_score` (default 70)
- `min_source_confidence` (default 0.70)

Report eligibility requires all of: scores above thresholds, non-excluded vertical, not a known duplicate, and present `evidence_text` + `source_url` when required.

## Dashboard

Routes (FastAPI + Jinja2):

| Path | View |
|------|------|
| `/novelty` | Overview + recent results |
| `/novelty/new` | New / needs-review candidates |
| `/novelty/known` | Known duplicates, near duplicates, generic |
| `/novelty/noise` | Noise, weak evidence, excluded |
| `/opportunities` | Report-eligible `keyword_opportunities` |
| `/opportunities/digest-preview` | Dry-run Telegram digest text (no send) |
| `/opportunities/batch-review` | Latest batch summary and grouped review |
| `/sources/landing-pages` | Landing page import results and top opportunities |
| `/novelty/known-pending` | Queued known-term promotions (DB only) |

## Manual import (research → novelty engine)

Use **`scripts/import_discovery_candidates.py`** to load manually curated outputs from Grok, Perplexity, SERP notes, Reddit threads, landing pages, or operator research — without live collectors.

### Sample input

See **`examples/discovery_candidates.sample.json`**. Top-level JSON **array** of objects:

```json
[
  {
    "candidate_text": "dog ACL surgery payment plan",
    "candidate_type": "use_case",
    "vertical": "pet_financing",
    "sub_vertical": "dog_surgery",
    "source_type": "reddit",
    "source_url": "https://example.com/thread/1",
    "evidence_text": "The vet quoted $4,800 for ACL surgery and asked if I needed a payment plan.",
    "source_confidence": 0.85
  }
]
```

**Required fields:** `candidate_text`, `candidate_type`, `vertical`, `source_type`, `evidence_text`, `source_confidence`.

**Optional:** `sub_vertical`, `source_url`, `extraction_confidence`, `title`, `author_or_publisher`, `market`, `state`, `published_at`.

The importer:

1. Validates each record
2. Inserts `raw_discovery_items` (full record JSON in `raw_json`)
3. Inserts `candidate_terms` (via `novelty_engine.process_candidate`)
4. Writes `novelty_results` and `keyword_opportunities` when report-eligible

### Dry-run

Evaluate and print a summary **without DB writes**:

```bash
.venv\Scripts\python scripts/import_discovery_candidates.py ^
  --input examples/discovery_candidates.sample.json ^
  --dry-run
```

Summary columns: total input, processed, report eligible, suppressed known/generic/excluded, errors.

### Import to database

```bash
.venv\Scripts\python -c "from shared.db import migrate; migrate('data/pipeline.db')"

.venv\Scripts\python scripts/import_discovery_candidates.py ^
  --db data/pipeline.db ^
  --input examples/discovery_candidates.sample.json
```

Known brands, generic keywords, and excluded verticals are stored and visible in the dashboard but **not** added to `keyword_opportunities`.

### Digest preview workflow

1. Import candidates (or process via `process_candidate`).
2. Open **`/opportunities`** to review report-eligible rows.
3. Open **`/opportunities/digest-preview`** to see the formatted Telegram digest (`format_pending_digest`) — **no Telegram send**.
4. Open **`/opportunities/batch-review`** after running a tagged research batch to inspect status counts, suppression reasons, score distribution, and grouped candidates.
5. Use review actions on **`/opportunities`**, **`/opportunities/batch-review`**, and **`/novelty`** to triage items before any Telegram send.

## Operator review workflow

Dashboard POST actions (simple form POST + redirect, no Telegram send):

| Action | Route | Effect |
|--------|-------|--------|
| Approve | `POST /opportunities/{id}/approve` | `keyword_opportunities.status = approved` |
| Reject | `POST /opportunities/{id}/reject` | `status = rejected`, removed from digest |
| Archive | `POST /opportunities/{id}/archive` | `status = archived`, hidden from digest |
| Mark noise | `POST /novelty/{id}/mark-noise` | `novelty_status = noise`, linked opportunity `status = noise` |
| Add to known | `POST /novelty/{id}/add-to-known` | queues row in `known_terms_pending` |

Every action writes an audit row to **`novelty_review_actions`**. No rows are deleted.

### Status meanings

**`keyword_opportunities.status`**

| Status | Meaning |
|--------|---------|
| `new` | Report-eligible, awaiting review (included in default digest) |
| `approved` | Operator accepted (excluded from default digest; optional via `include_approved=True`) |
| `rejected` | Operator declined (excluded from digest) |
| `archived` | Closed / filed away (excluded from digest) |
| `noise` | Manually marked noise (excluded from digest) |

**`novelty_results.reviewed_status`**

| Status | Meaning |
|--------|---------|
| `pending` | Engine default — no operator action yet |
| `approved` / `rejected` / `archived` / `noise` | Mirrors opportunity review outcome |
| `known_pending` | Queued for known-list promotion |

### Known terms pending

Route: **`/novelty/known-pending`**

When you click **Known** on a novelty row, the term is stored in **`known_terms_pending`** with `status = pending`. This phase does **not** write to `config/known_entities.yaml` or `config/known_keywords.yaml` automatically — that keeps YAML edits explicit and reviewable. A later phase can promote pending rows into config after operator confirmation.

### Digest rules (dry-run)

`format_pending_digest` includes only opportunities where:

- `keyword_opportunities.status = new` (default)
- scores meet thresholds
- linked `novelty_results` are not `rejected`, `noise`, or `archived`

Pass `include_approved=True` to preview approved items too. Telegram auto-send remains disabled.

## Research batch validation

Use a **real curated batch** to evaluate novelty scoring quality before trusting outbound alerts.

### Sample batch

**`data/imports/research_batch_001.sample.json`** contains 30 mixed candidates:

- Known national brands (CareCredit, SoFi, Klarna, Sunbit)
- Generic keywords (`personal loan`, `pet financing`, …)
- Excluded verticals (`title_loan`, `payday_loan`, `insurance`, …)
- Weak evidence (missing URL, low confidence)
- Strong new use-case phrases
- Local/regional brand candidates
- Landing-page offer angles
- Reddit-style consumer pain phrases

Each record should include `"batch_id": "research_batch_001"` so the dashboard can group results.

### Run a batch

Dry-run (no DB writes, still writes CSV if requested):

```bash
.venv\Scripts\python scripts/validate_research_batch.py ^
  --input data/imports/research_batch_001.sample.json ^
  --dry-run ^
  --csv
```

Import to SQLite and write CSV + meta JSON:

```bash
.venv\Scripts\python scripts/validate_research_batch.py ^
  --db data/pipeline.db ^
  --input data/imports/research_batch_001.sample.json ^
  --csv
```

Outputs (generated locally, gitignored):

- `data/imports/research_batch_001.results.csv` — per-candidate scores and suppression reasons
- `data/imports/research_batch_001.meta.json` — batch summary for CLI/dashboard reference

### Interpreting results

| Output | Meaning |
|--------|---------|
| **Report eligible** | Would become `keyword_opportunities` — review these first |
| **Suppressed known** | Matches `config/known_entities.yaml` (exact or fuzzy) |
| **Suppressed generic** | Matches `config/known_keywords.yaml` |
| **Suppressed excluded** | Vertical in `config/excluded_verticals.yaml` |
| **weak_evidence** | Missing required URL/text or low confidence vs rules |
| **Score distribution** | Sanity-check that novel phrases cluster higher than noise |

Open **`/opportunities/batch-review`** after import to compare CLI CSV with the dashboard view.

## Landing page import

The first real source importer fetches a **manual URL list**, extracts visible marketing text, derives candidate phrases, and runs them through the novelty engine. It is conservative by design: no crawler, no paywall/login bypass, no robots evasion.

### Input format

See **`examples/landing_pages.sample.json`**. Top-level JSON **array**:

```json
[
  {
    "url": "https://example.com/vet-financing",
    "vertical": "pet_financing",
    "source_confidence": 0.85,
    "notes": "Sample landing page"
  }
]
```

**Required fields:** `url`, `vertical`, `source_confidence`.

**Optional:** `notes`.

### What gets extracted

From each fetched page (when HTTP succeeds):

- Page title and meta description
- H1/H2/H3 headings
- CTA button/link text
- FAQ summary lines
- Form labels
- Short paragraphs (20–320 chars)
- Disclosure snippets with financing signals

Navigation and footer regions are skipped where possible. Obvious boilerplate (`apply now`, `privacy policy`, `contact us`, …) is suppressed. Phrases must match financing/use-case signals before becoming candidates.

### Dry-run

Evaluate without DB writes; optionally write CSV/meta:

```bash
.venv\Scripts\python scripts/import_landing_pages.py ^
  --input examples/landing_pages.sample.json ^
  --dry-run ^
  --max-pages 10 ^
  --max-candidates-per-page 50 ^
  --csv
```

### Import to database

```bash
.venv\Scripts\python scripts/import_landing_pages.py ^
  --db data/pipeline.db ^
  --input examples/landing_pages.sample.json ^
  --csv
```

Outputs (generated locally):

- `data/imports/landing_pages.results.csv` — per-candidate scores, suppression reasons, evidence text
- `data/imports/landing_pages.meta.json` — page/candidate counts and top opportunities

### Review workflow after import

1. Open **`/sources/landing-pages`** for imported URLs, candidate counts, suppressed vs report-eligible totals, and top opportunities with evidence.
2. Open **`/opportunities`** to approve/reject/archive report-eligible rows.
3. Use **`/opportunities/digest-preview`** for dry-run digest text only (no Telegram send).

### Limitations

- Manual URL list only — no site-wide crawling or link following.
- Single-page fetch with a 15s timeout and explicit user agent.
- Pages behind login, paywalls, or bot protection may fail and are recorded as errors.
- Respects conservative fetching; does not bypass `robots.txt` or rate limits aggressively.
- Does not integrate with the radio worker or Telegram auto-send.

### Tuning known lists

When legitimate new phrases are suppressed as **generic** or **known_duplicate**:

1. Confirm the phrase is truly novel — do not remove generic terms prematurely.
2. Add **brands only** to `config/known_entities.yaml` under the correct vertical family.
3. Add **generic finance head-terms** to `config/known_keywords.yaml`.
4. Re-run the same batch with `--dry-run` and compare CSV deltas.

Near-duplicate sensitivity is controlled by `thresholds.near_duplicate_ratio` (default 85) in `config/novelty_rules.yaml`.

### Tuning novelty_rules.yaml

| Key | Effect |
|-----|--------|
| `report_novelty_score` | Minimum novelty score for report eligibility |
| `report_opportunity_score` | Minimum opportunity score for report eligibility |
| `min_source_confidence` | Minimum source confidence from import JSON |
| `near_duplicate_ratio` | Fuzzy match threshold vs known brands/keywords |
| `dashboard_only_score` | Score band for generic/near-duplicate rows |
| `noise_score` | Score assigned to empty/noise text |
| `reporting.require_evidence_text` | Require `evidence_text` in import JSON |
| `reporting.require_source_url` | Require `source_url` for report eligibility |

After rule changes, re-run `validate_research_batch.py` on the same JSON and diff the CSV.

## Reporting

- **`alerter/novelty_reporter.py`** formats pending `keyword_opportunities` where `status = 'new'` and scores meet thresholds.
- Tracer bullet: **dry-run formatter only** — does not auto-send Telegram. Integrate with the existing alerter when ready.

## Database

Migration: **`shared/migrations/019_novelty_engine.sql`** (numbered 019 because 017/018 are used by station control/pool migrations).

Tables:

- `raw_discovery_items` — raw collector payloads (future)
- `candidate_terms` — extracted candidate phrases
- `novelty_results` — classification + scores
- `keyword_opportunities` — report-eligible rows only

Apply migrations:

```bash
.venv\Scripts\python -c "from shared.db import migrate; migrate('data/pipeline.db')"
```

## Processing sample candidates

```python
from worker.novelty_engine import CandidateInput, process_candidate

process_candidate(
    "data/pipeline.db",
    CandidateInput(
        candidate_text="dog ACL surgery payment plan",
        vertical="pet_financing",
        source_type="manual",
        source_url="https://example.com/thread/1",
        evidence_text="Looking for payment options after vet quote.",
        source_confidence=0.85,
    ),
)
```

## Adding known brands / keywords

1. Edit `config/known_entities.yaml` (brands) or `config/known_keywords.yaml` (generic phrases).
2. Restart any long-lived workers that cache config (novelty engine loads YAML per call by default).
3. Re-run evaluation on existing candidates if you need to refresh stored results.

## Running tests

```bash
.venv\Scripts\pytest tests/test_novelty_engine.py tests/test_discovery_import.py tests/test_batch_validation.py tests/test_novelty_review.py tests/test_db.py tests/test_dashboard.py -q
```

## Out of scope (this pass)

- SERP / Reddit / X collectors
- Radio worker integration
- Automatic Telegram send (use `format_pending_digest` for dry-run review)
