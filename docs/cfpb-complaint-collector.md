# CFPB Consumer Complaint Trademark Collector

## What this is

The CFPB Consumer Complaint Trademark Collector ingests filtered records from the [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) and produces **reviewable trademark/brand seed candidates** for the project's Trademark Keyword Research Layer.

## What this is not

- **Not** generic radio keyword discovery
- **Not** proof that a company is currently advertising on radio
- **Not** legal or trademark clearance advice
- **Not** an auto-approval pipeline — all CFPB-derived names are **leads only**

CFPB complaints are consumer-provided, not a statistical sample, and complaint volume does not represent market share.

## Docker (compose profile `cfpb`)

```powershell
docker compose --profile cfpb run --rm cfpb-collector
```

Or wrapper:

```powershell
.\scripts\run-cfpb-collector.ps1 -Docker
```

Requires `pipeline-migrate` (runs automatically as dependency). Uses ingestor image (no GPU).

Configuration: `config/cfpb_collector.yaml`

| Option | Description |
|---|---|
| `enabled` | Master switch |
| `source_mode` | `api` or `bulk_csv` |
| `target_states` | US state codes (TX, CA, …) |
| `target_products` | CFPB product categories |
| `date_from` / `date_to` | Date received filter |
| `batch_size` | SQLite insert batch size |
| `max_records_per_run` | Cap per run |
| `rate_limit_sleep_seconds` | API politeness delay |
| `include_narratives` | Extract from consumer narratives |
| `min_company_complaint_count` | Entity aggregation threshold |
| `output_to_trademark_layer` | Bridge strong entities to trademark tables |
| `bulk_csv_path` | Path when `source_mode: bulk_csv` |
| `auto_approve_enabled` | Auto-approve seeds at/above threshold (default **true** in repo config) |
| `auto_approve_min_score` | Min score for auto-approve (default **85**); excludes narrative/domain types |

## Database tables

| Table | Purpose |
|---|---|
| `cfpb_complaints_raw` | Raw complaint rows (deduped by `complaint_id`) |
| `cfpb_company_entities` | Aggregated company metrics and scores |
| `cfpb_brand_candidates` | Extracted brand/trademark seed candidates |
| `cfpb_collection_runs` | Audit trail per collector run |
| `trademark_entities` | Canonical trademark layer (WP-0 foundation) |
| `trademark_aliases` | Alternate names |
| `trademark_keyword_candidates` | Conservative keyword variants |

Migrations: `006_trademark_layer.sql`, `007_cfpb_collector.sql`

## Scoring

Entity and candidate scores range **0–100**:

| Band | Meaning |
|---|---|
| 85–100 | Strong trademark/entity seed |
| 70–84 | Good seed |
| 50–69 | Review |
| 30–49 | Weak |
| 0–29 | Reject/noise |

Factors: complaint volume, state coverage, product relevance, narrative evidence, recency, generic-name penalties.

## Review workflow

1. Run collector → candidates default to `needs_verification` (or `approved_seed` when auto-approve on)
2. Review in dashboard: `/cfpb`, `/cfpb/candidates`, `/cfpb/candidates/{id}`
3. Actions: approve as seed, reject as noise, mark needs verification
4. Strong entities (score ≥ 70) optionally bridge to `trademark_entities` with:
   - `source_type = cfpb_complaint`
   - `review_status = new` or `approved_seed` (if auto-approve enabled)
   - `ad_copy_allowed = false` always
   - Conservative variants: `{brand} reviews`, `{brand} complaints`, etc.

**Auto-approve (opt-in):** `auto_approve_enabled: true` + `auto_approve_min_score: 85` in config approves company-field candidates only — never narrative/domain extractions. **`ad_copy_allowed` stays false.**

Verify with radio transcripts, SERP ads, or landing pages before operational ad use.

## CSV export

```powershell
.venv\Scripts\python scripts/export_cfpb_brand_candidates.py -o data/cfpb_brand_candidates.csv
.venv\Scripts\python scripts/export_cfpb_brand_candidates.py --min-score 70
```

## Dashboard routes

- `/cfpb` — overview
- `/cfpb/runs` — collection run history
- `/cfpb/entities` — company entities
- `/cfpb/candidates` — brand candidates
- `/cfpb/candidates/{id}` — detail + review actions

## Limitations

- Narrative extraction uses conservative regex (no LLM in collector path)
- Fuzzy company merge is **not** automatic — use dashboard merge when uncertain
- Bulk CSV mode streams rows; very large files may take time on first backfill
- CFPB API availability and rate limits apply to `source_mode: api`

## Integration with radio pipeline

CFPB seeds supplement — they do not replace — radio-derived ad detection and keyword hits. Cross-reference CFPB candidates against:

- `detections.company_name` from radio LLM extraction
- `keyword_hits` from transcript scanning
- External SERP/landing-page verification (manual)
