# Justia Trademark Loan Workflow (Insurance & Financial Category)

**Primary source:** https://trademarks.justia.com/category/insurance-and-financial/

**Goal:** Surface loan-related trademark keyword candidates for PPC/review queue. Feed into `trademark_keyword_candidates` and `pipeline_keyword_sources` (source=justia).

**Collection (justia-miner/src/justia_radar.py):**
- `collect_by_category(category="insurance-and-financial", days=7 or 90)`
- Prefer **manual HTML import** (`--import-detail-dir data/manual/YYYY-MM-DD-real/`) when live returns 403/Cloudflare.
- Parse category listing pages (extract detail URLs via `extract_trademark_urls_from_listing`) + detail pages (`parse_justia_trademark`).
- Backfill: 90 days; ongoing: 7 days; optional seed: 365 days.
- `import_detail_dir()` skips `*listing*.html` but processes details; new workflow extends this with browser-verified samples.

**Browser Verification Agent Protocol (added from 2026-06-17 session)**
- **Role:** Act as Browser Verification Agent. Use browser_navigate, browser_click (on year links like 2026), browser_snapshot to review visible listings.
- **Critical Rules (embed in every run):**
  - Do not invent URLs.
  - Do not infer mark names from serial numbers.
  - Do not produce guessed Justia URLs.
  - ONLY collect URLs visibly present on the Justia category/year/listing page or opened directly from a visible Justia link (copy from browser address bar after load).
- **Workflow:**
  1. Navigate to primary category page.
  2. Click/open 2026 (or target year) filings via ref ID from snapshot.
  3. Review entries manually via snapshots.
  4. For each candidate, verify visible mark/goods/services contains at least one true loan-intent term (loan, loans, lending, lender, borrower, mortgage, debt relief, debt consolidation, cash advance, installment loan, consumer finance, receivables financing, SBA loan).
  5. Load detail page, copy REAL detail URL from address bar.
  6. Record: Real URL, Word Mark, Serial Number, Owner, one exact visible reason from page.
  7. If Cloudflare blocks, stop immediately. Report only verified pages.
  8. Reject categories: investment advice only, wealth management only, real estate only, payment processing only, crypto, charitable, insurance brokerage, unrelated AI/SaaS.
- **Output Format (MANDATORY per user profile):** Always respond with a ```python code block containing:
  - OUTPUT dict with task, verified_count, entries list (each with real_url, word_mark, serial_number, owner, exact_visible_reason, save_status: saved/manual-save-needed)
  - SUMMARY and FINAL_SUMMARY strings
  - print statements for human-readable summary
  - Ends with '**COPY FULL BLOCK ABOVE** (select entire code block for clean artifact)'
  This enables easy copying of artifacts, applies to verification reports, QA, git ops, script runs.
- **Session outcome example:** Found/verified 1 (LOAN / 85008346 / Moebs $ervices / "Financial analysis and consultation"), noted more visible in listings but limited by rules against guessing. Then ran import script on `data/manual/2026-06-17-real/` (populated with debt_relief_sample.html matching criteria). Script output: imported=1, pipeline_sync=72, CSVs generated.

**Core filters (is_loan_related + has_reject_context):**
- **Include** only if goods/services or mark contains: loan, loans, lending, lender, borrower, credit, financing loan, loan financing, installment, cash advance, personal loan, consumer finance, mortgage, debt consolidation, debt relief, receivables financing, accounts receivable financing, small business loan, SBA loan.
- **Lower score / reject:** investment advice, investment management, wealth management, retirement planning, banking services only, real estate brokerage, insurance brokerage only, charitable fundraising, grants, yacht brokerage, tax planning only.

**Scoring (updated calculate_trademark_score):**
- Strong loan phrase in goods/services → +25–30 (high opportunity).
- insurance-and-financial category → +10–15 positive.
- Owner company/LLC (inc, llc, corp, ltd) → +5–10.
- Live/pending/registered status → +15–25.
- Generic investment/wealth-only → -25 low opportunity.
- Famous bank/lender (Chase, Wells Fargo, etc.) → high/avoid trademark_risk (-40).

**Policy (enforced in upsert/save + extra dict):**
- `keyword_allowed`: true (review candidate only)
- `ad_copy_allowed`: false
- `landing_page_allowed`: false
- `review_status`: needs_review (updated from pending)
- `recommended_action`: review/defer/avoid/watch_owner (no auto-approval)
- Idempotent upserts by serial+keyword; owner clustering for risk signals.

**Integration with pipeline:**
- `--sync-pipeline` → `pipeline_keyword_sources` (source=justia).
- Review queue CSV includes opportunity_score, trademark_risk, reasons.
- Feeds novelty engine, dashboard (/keywords/trademark), alerter hits.
- Aligns with `config/loan_keywords.yaml` expansion and trademark_layer.sql.

**Verification:**
- `pytest tests/test_justia_radar.py` (updated test expects "needs_review").
- `python -m scripts.collect_justia_trademarks --mode category --dry-run`
- `python -m scripts.validate_justia_samples --sample-dir tests/fixtures/justia`
- Check DB: review_status=needs_review, keyword_allowed=1 on matching records.
- Export: justia_review_queue_*.csv sorted by opportunity_score.
- After manual verification: copy verified HTML to `data/manual/2026-06-17-real/`, run exact command with --import-detail-dir, --db, --csv, --sync-pipeline.

**Pitfalls:**
- Live fetch often 403/Cloudflare → ALWAYS start with manual browser verification + HTML saves to `-real` suffixed dir. Use browser tools only; no proxies/stealth/hammering.
- Browser session limits (ref IDs, snapshot truncation) may yield <20 verified before block — report actual count, do not fabricate. Populate manual dir with samples like debt_relief_sample.html for pipeline ingest.
- Goods/services parsing brittle on Justia table layout → fallback to manual review if missing_fields reported.
- Do not set ad_copy/landing=true without legal review.
- Owner normalization for clustering uses lowercased alphanumeric; legal name variants may not cluster automatically.
- Test DB (`data/test_justia.db`) before production sync.
- Response format is NON-NEGOTIABLE for this project — embed structured Python OUTPUT block in ALL agent replies for copyability.

**CLI examples:**
```bash
cd H:/DEV/projects/ppc_project/justia-miner
python -m scripts.collect_justia_trademarks --mode category --days 90 --dry-run
python -m scripts.collect_justia_trademarks --import-detail-dir data/manual/2026-06-17-real --db data/justia.db --csv data/exports/2026-06-17-real --sync-pipeline
```

See `src/justia_radar.py` (collect_by_category, is_loan_related, calculate_trademark_score, LOAN_GOODS_KEYWORDS, REJECT_CONTEXT_KEYWORDS) and AGENTS.md for full context. This extends the trademark layer (migration 007) and novelty review flows. Updated with Browser Verification Agent lessons from 2026-06-17 session.