# Justia Name-Only Collector Reference

**Script:** `scripts/discover_justia_names_via_apify.py`

**Purpose:** Maximum-recall collection of potential trademark/brand names from Justia via Apify Google SERP. No verification, no scoring, no rejection of mortgage/debt/investment names. Operator reviews output manually.

**Query config:** `config/justia_name_queries.txt` (26 broad queries)
- All contain `site:trademarks.justia.com`
- Examples: "loan", "loans", "lending", "cash advance", "personal loan", "title loan", "installment loan", "loan services", "lines of credit"
- No heavy negative terms (-mortgage etc. only in narrow optional queries)
- No mandatory "Goods and Services" phrase

**Name extraction logic:**
1. `extract_mark_name(title)`: text before first " - " or "|", strip Justia suffixes.
2. `extract_slug_name(url)`: first slug component before serial (e.g. "kroma" from /kroma-97229924.html).
3. `normalize_name()`: upper, alphanumeric only, collapse spaces.
4. Keep both original title and extracted name.
5. Serial via regex on URL path.

**Filtering (minimal):**
- Reject only if URL contains lawyers.justia.com or contracts.justia.com.
- Accept ALL others (including mortgage, debt, investment, bank names).

**Deduplication:** by (normalized_name, serial, url). Prefer lowest position.

**Output columns (CSV/JSONL):**
- detected_mark_name
- detected_serial_number
- url
- title
- snippet
- query
- position
- source (apify_google_serp)
- review_status (raw_candidate)
- contains_loan_term, matched_terms, normalized_name, url_slug_name (helpful)

**CLI for smoke test:**
```bash
cd H:\DEV\projects\ppc_project\justia-miner
python scripts/discover_justia_names_via_apify.py --dry-run --debug
```

**Real run:**
```bash
python scripts/discover_justia_names_via_apify.py ^
  --token %APIFY_TOKEN% ^
  --max-results-per-query 10 ^
  --output data/apify/justia_name_candidates.jsonl ^
  --csv data/apify/justia_name_candidates.csv ^
  --debug
```

**When to use this skill:**
- Operator says "do not want deep verification", "just collect names", "simplify to name-only", "as many potential brands as possible".
- When Browser Verification Agent is repeatedly blocked by Cloudflare.
- Goal is volume for later manual curation.

**Pitfall:** Do not add strict loan-only filtering or USPTO calls in this mode — it defeats the "recall-first, operator reviews" intent.

**Related:** See main Justia section in SKILL.md for full pipeline integration path (names → manual review → verification → import).