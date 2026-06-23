import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

try:
    from apify_client import ApifyClient
    APIFY_AVAILABLE = True
except ImportError:
    APIFY_AVAILABLE = False


def load_queries(path: str = "config/justia_name_queries.txt") -> List[str]:
    queries = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                queries.append(line)
    return queries


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    return ' '.join(name.upper().split())


def extract_serial_from_url(url: str) -> str:
    match = re.search(r'-(\d{7,8})(?:\.html)?(?:[?#]|$)', url or '')
    if match:
        return match.group(1)
    match = re.search(r'/(\d{7,8})(?:[/?#]|$)', url or '')
    if match:
        return match.group(1)
    return ""


def extract_mark_from_title(title: str) -> str:
    if not title:
        return ""
    if ' - ' in title:
        return title.split(' - ', 1)[0].strip()
    if '-' in title:
        return title.split('-', 1)[0].strip()
    return title.strip()


def extract_slug_name(url: str) -> str:
    if not url:
        return ""
    match = re.search(r'/([a-zA-Z0-9-]+?)-?\d', url)
    if match:
        slug = match.group(1).replace('-', ' ')
        return slug.upper().strip()
    return ""


def run_apify(queries: List[str], max_results_per_query: int = 10, token: str = None) -> List[Dict]:
    if not token or not APIFY_AVAILABLE:
        print("DRY-RUN MODE: Using mocked SERP results (no Apify call)")
        mock_results = []
        for i, q in enumerate(queries[:3]):
            mock_results.append({
                "query": q,
                "title": f"LOAN BRAND {i+1} - Sample Loan Services",
                "url": f"https://trademarks.justia.com/87{i}/23/loan-brand-{i}23456.html",
                "snippet": "Loan services and financing products",
                "position": i+1,
                "organicResults": [{"title": f"LOAN BRAND {i+1}", "url": f"https://trademarks.justia.com/87{i}/23/loan-brand-{i}23456.html", "description": "Loan services"}]
            })
        return mock_results

    client = ApifyClient(token)
    run_input = {
        "queries": "\n".join(queries),
        "resultsPerPage": max_results_per_query,
        "maxPagesPerQuery": 1,
        "countryCode": "us",
        "languageCode": "en",
        "includeUnfilteredResults": False,
        "saveHtml": False,
    }

    run = client.actor("apify/google-search-scraper").call(run_input=run_input, wait_duration=300)
    dataset_id = None
    if hasattr(run, "default_dataset_id"):
        dataset_id = run.default_dataset_id
    elif isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")

    if not dataset_id:
        print("Warning: Could not get dataset ID")
        return []

    items = list(client.dataset(dataset_id).iterate_items())
    return items


def check_overwrite_safety(output_path: Path, csv_path: Path, append: bool, force: bool) -> None:
    """Safety guard to prevent accidental overwrite of existing non-empty output."""
    jsonl_exists = output_path.exists() and output_path.stat().st_size > 0
    csv_exists = csv_path.exists() and csv_path.stat().st_size > 0

    if (jsonl_exists or csv_exists) and not append and not force:
        print("Output file already exists and contains data.")
        print("Use --append to add candidates or --force-overwrite to replace it.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None)
    parser.add_argument("--max-results-per-query", type=int, default=10)
    parser.add_argument("--output", default="data/apify/justia_name_candidates.jsonl")
    parser.add_argument("--csv", default="data/apify/justia_name_candidates.csv")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--query-limit", type=int, default=None)
    parser.add_argument("--query-offset", type=int, default=0)
    parser.add_argument("--shuffle-queries", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--force-overwrite", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    csv_path = Path(args.csv)

    # Safety guard
    check_overwrite_safety(output_path, csv_path, args.append, args.force_overwrite)

    queries = load_queries()
    if args.query_limit:
        queries = queries[:args.query_limit]
        if args.debug:
            print(f"Limited to first {args.query_limit} queries")

    if args.debug:
        print(f"Loaded {len(queries)} name collection queries from config/justia_name_queries.txt")

    # Load existing for append mode
    existing_names = set()
    existing_serials = set()
    if args.append and csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('detected_mark_name'):
                    existing_names.add(normalize_name(row['detected_mark_name']))
                if row.get('detected_serial_number'):
                    existing_serials.add(row['detected_serial_number'])

    results = run_apify(queries, args.max_results_per_query, args.token)
    candidates = []

    for item in results:
        if "organicResults" in item:
            for r in item.get("organicResults", []):
                title = r.get("title") or item.get("title", "")
                url = r.get("url") or item.get("url", "")
                snippet = r.get("description") or r.get("snippet") or item.get("snippet", "")
                query = item.get("searchQuery", {}).get("term") or item.get("query", "")
                position = r.get("position") or item.get("position", 0)

                if "lawyers.justia.com" in url or "contracts.justia.com" in url:
                    continue

                mark_from_title = extract_mark_from_title(title)
                serial = extract_serial_from_url(url)
                slug_name = extract_slug_name(url)

                normalized = normalize_name(mark_from_title or slug_name)
                if normalized in existing_names or (serial and serial in existing_serials):
                    continue

                candidate = {
                    "detected_mark_name": mark_from_title or slug_name or "UNKNOWN",
                    "detected_serial_number": serial,
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "query": query,
                    "position": position,
                    "source": "apify_google_serp",
                    "review_status": "raw_candidate",
                    "manual_decision": "",
                    "notes": "",
                    "normalized_name": normalized,
                    "url_slug_name": slug_name,
                    "contains_loan_term": any(term in (snippet + title + query).lower() for term in ["loan", "lending", "cash advance", "title loan"])
                }
                candidates.append(candidate)
                existing_names.add(normalized)
                if serial:
                    existing_serials.add(serial)
        else:
            title = item.get("title", "")
            url = item.get("url", "")
            if "lawyers.justia.com" in url or "contracts.justia.com" in url:
                continue
            mark_from_title = extract_mark_from_title(title)
            serial = extract_serial_from_url(url)
            slug_name = extract_slug_name(url)
            normalized = normalize_name(mark_from_title or slug_name)
            if normalized in existing_names or (serial and serial in existing_serials):
                continue

            candidate = {
                "detected_mark_name": mark_from_title or slug_name or "UNKNOWN",
                "detected_serial_number": serial,
                "url": url,
                "title": title,
                "snippet": item.get("snippet", ""),
                "query": item.get("query", ""),
                "position": item.get("position", 0),
                "source": "apify_google_serp",
                "review_status": "raw_candidate",
                "manual_decision": "",
                "notes": "",
                "normalized_name": normalized,
                "url_slug_name": slug_name,
                "contains_loan_term": True
            }
            candidates.append(candidate)
            existing_names.add(normalized)
            if serial:
                existing_serials.add(serial)

    # === ATOMIC WRITE + VERIFICATION ===
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "detected_mark_name", "detected_serial_number", "url", "title", "snippet",
        "query", "position", "source", "review_status", "manual_decision", "notes",
        "normalized_name", "url_slug_name", "contains_loan_term"
    ]

    # Write JSONL atomically
    jsonl_tmp = output_path.with_suffix(".jsonl.tmp")
    with open(jsonl_tmp, 'w', encoding='utf-8') as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    jsonl_tmp.replace(output_path)

    # Write CSV atomically
    csv_tmp = csv_path.with_suffix(".csv.tmp")
    with open(csv_tmp, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            row = {k: c.get(k, "") for k in fieldnames}
            writer.writerow(row)
    csv_tmp.replace(csv_path)

    # === POST-WRITE VERIFICATION ===
    jsonl_exists = output_path.exists()
    csv_exists = csv_path.exists()
    jsonl_size = output_path.stat().st_size if jsonl_exists else 0
    csv_size = csv_path.stat().st_size if csv_exists else 0

    jsonl_lines = 0
    csv_lines = 0
    if jsonl_exists:
        jsonl_lines = sum(1 for _ in output_path.open(encoding='utf-8'))
    if csv_exists:
        csv_lines = sum(1 for _ in csv_path.open(encoding='utf-8'))

    expected_jsonl = len(candidates)
    expected_csv = len(candidates) + 1

    verification_passed = True
    if len(candidates) > 0:
        if jsonl_size == 0 or jsonl_lines != expected_jsonl:
            verification_passed = False
        if csv_size == 0 or csv_lines != expected_csv:
            verification_passed = False

    if not verification_passed:
        print("!!! POST-WRITE VERIFICATION FAILED !!!")
        raise RuntimeError("Output files are empty or line count mismatch after write")

    if args.debug:
        print(f"Discovery complete. Wrote {len(candidates)} name candidates.")
        print(f"Absolute paths:")
        print(f"  JSONL: {output_path.resolve()}")
        print(f"  CSV:   {csv_path.resolve()}")
        print(f"Verified from disk:")
        print(f"  jsonl_lines: {jsonl_lines}")
        print(f"  csv_lines: {csv_lines}")
        print(f"  jsonl_size_bytes: {jsonl_size}")
        print(f"  csv_size_bytes: {csv_size}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
