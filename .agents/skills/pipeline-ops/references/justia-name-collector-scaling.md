# Justia Name-Only Collector Scaling Pattern (v2)

**When to use**: Operator wants maximum raw trademark/brand name volume from Justia/Google SERP before any review ("do not want deep verification", "just collect names", "scale discovery volume").

**Core script**: `scripts/discover_justia_names_via_apify.py`

**Query config**: `config/justia_name_queries.txt` (150+ broad recall-first queries, minimal negatives, no mandatory "Goods and Services")

**Key CLI flags for scaling**:
- `--query-limit N` — process only first N queries (for testing)
- `--query-offset N` — start from query index N (for batching large corpus)
- `--shuffle-queries` — randomize order (with fixed seed for reproducibility in tests)
- `--append` — append to existing output while deduplicating by normalized_name/serial/URL
- `--max-results-per-query 20..100` — higher recall per query

**Output**:
- `data/apify/justia_name_candidates.jsonl` + `.csv`
- New columns: `manual_decision` (blank), `notes` (blank) for human review
- `data/apify/justia_name_candidates.meta.json` with run metadata (started_at, queries_processed, final_candidates_written, absolute paths, etc.)

**Post-write verification (mandatory)**:
After every write:
1. Confirm both JSONL and CSV exist
2. JSONL line count == final_candidates_written
3. CSV line count == final_candidates_written + 1 (header)
4. CSV has header row with all stable columns
5. If any check fails → exit(1) with clear error. Never claim "success" if files are missing.

**Critical lesson from multiple sessions (2026-06-17 to 06-18)**:
Scripts frequently printed "Wrote X candidates" and "SUCCESS" while the actual files were 0 bytes or did not exist (data/apify directory missing, silent exceptions before write, wrong cwd). 

**ALWAYS** run post-write verification and `dir data\apify` / `Get-ChildItem` / line count checks before claiming success in reports. Explicitly create `data/apify` directory if it does not exist before any write.

**Extraction rules (lightweight)**:
- Prefer text before first " - " or "-" in title for detected_mark_name
- Extract serial from Justia URL pattern
- Extract slug name from URL for additional candidate
- Keep raw title, snippet, query, position
- Only hard reject: lawyers.justia.com, contracts.justia.com
- Keep ALL finance-adjacent names (mortgage, debt, investment, bank, etc.) for manual review

**Mandatory response format for this profile**:
Every response (discovery, verification, collection, status) must be wrapped in a ```python code block containing:
- OUTPUT = {structured dict with task, counts, entries, summary fields}
- SUMMARY and FINAL_SUMMARY strings
- Human-readable print sections (=== TITLE ===, counts, lists)
- Must end with exact text: **COPY FULL BLOCK ABOVE** (select entire code block for clean artifact)

This format is non-negotiable for the justia-coder profile. All previous verification and discovery tasks used it.

**Typical workflow for maximum volume**:
1. `mkdir -Force data\apify`
2. Run collector with high --max-results-per-query (20-100), --query-limit 50 or full 150, --append for incremental corpus building
3. Review `justia_name_candidates.csv` manually (fill manual_decision column)
4. (Optional later) Use verified names for keyword expansion in pipeline

This pattern replaced the heavy Browser Verification Agent + USPTO fallback when Cloudflare made manual HTML saving non-scalable.

See `references/justia-trademark-loan-workflow.md` for the full evolution from strict verification to name-only recall mode.