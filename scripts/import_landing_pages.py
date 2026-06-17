#!/usr/bin/env python3
"""Import landing page URLs and extract novelty candidates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.db import migrate
from worker.landing_page_import import (
    format_landing_page_summary,
    import_landing_pages_file,
    write_landing_pages_csv,
    write_landing_pages_meta,
)

DEFAULT_IMPORTS_DIR = PROJECT_ROOT / "data" / "imports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import landing page URLs and extract novelty candidates.",
    )
    parser.add_argument("--db", default="data/pipeline.db", help="SQLite database path")
    parser.add_argument("--input", required=True, help="Path to landing page JSON list")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without DB writes")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum pages to import")
    parser.add_argument(
        "--max-candidates-per-page",
        type=int,
        default=50,
        help="Maximum candidate phrases per page",
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const="auto",
        help="Write results CSV (default: data/imports/landing_pages.results.csv)",
    )
    parser.add_argument(
        "--meta",
        action="store_true",
        help="Write summary metadata JSON (default when --csv is used)",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    db_path = Path(args.db)
    if not args.dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        migrate(db_path)

    report = import_landing_pages_file(
        db_path,
        input_path,
        dry_run=args.dry_run,
        max_pages=max(1, args.max_pages),
        max_candidates_per_page=max(1, args.max_candidates_per_page),
    )
    print(format_landing_page_summary(report))

    if args.csv is not None:
        csv_path = (
            DEFAULT_IMPORTS_DIR / "landing_pages.results.csv"
            if args.csv == "auto"
            else Path(args.csv)
        )
        write_landing_pages_csv(report, csv_path)
        print(f"\nWrote CSV: {csv_path}")

    if args.meta or args.csv is not None:
        meta_path = DEFAULT_IMPORTS_DIR / "landing_pages.meta.json"
        write_landing_pages_meta(report, meta_path)
        print(f"Wrote meta: {meta_path}")

    return 1 if report.errors and report.pages_processed == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
