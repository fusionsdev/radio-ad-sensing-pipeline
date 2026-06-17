#!/usr/bin/env python3
"""Import manually curated discovery candidates into the novelty engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.db import migrate
from worker.discovery_import import import_discovery_candidates_file


def _print_summary(summary, *, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "IMPORT"
    print(f"=== Discovery candidate {mode} ===")
    print(f"Total input:        {summary.total_input}")
    print(f"Processed:          {summary.processed}")
    print(f"Report eligible:    {summary.report_eligible}")
    print(f"Suppressed known:   {summary.suppressed_known}")
    print(f"Suppressed generic: {summary.suppressed_generic}")
    print(f"Suppressed excluded:{summary.suppressed_excluded}")
    print(f"Errors:             {len(summary.errors)}")
    for error in summary.errors:
        print(f"  - {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import external research candidates into raw_discovery_items and novelty engine.",
    )
    parser.add_argument(
        "--db",
        default="data/pipeline.db",
        help="SQLite database path (default: data/pipeline.db)",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JSON file containing candidate records",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and evaluate without writing to the database",
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

    summary = import_discovery_candidates_file(
        db_path,
        input_path,
        dry_run=args.dry_run,
    )
    _print_summary(summary, dry_run=args.dry_run)
    return 1 if summary.errors and summary.processed == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
