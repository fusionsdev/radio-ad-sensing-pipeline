#!/usr/bin/env python3
"""Validate a curated research candidate batch through the novelty engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.db import migrate
from worker.batch_validation import (
    format_batch_summary,
    run_batch_validation,
    write_batch_csv,
    write_batch_meta,
)

DEFAULT_IMPORTS_DIR = PROJECT_ROOT / "data" / "imports"


def _default_csv_path(input_path: Path, batch_id: str | None) -> Path:
    stem = batch_id or input_path.stem.replace(".sample", "")
    return DEFAULT_IMPORTS_DIR / f"{stem}.results.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import and summarize a curated research candidate batch.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to batch JSON file (e.g. data/imports/research_batch_001.sample.json)",
    )
    parser.add_argument(
        "--db",
        default="data/pipeline.db",
        help="SQLite database path (default: data/pipeline.db)",
    )
    parser.add_argument(
        "--batch-id",
        help="Optional batch identifier stored in raw_discovery_items (default: input stem)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate without writing to the database",
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const="auto",
        help="Write results CSV (optional path; default: data/imports/<batch>.results.csv)",
    )
    parser.add_argument(
        "--meta",
        action="store_true",
        help="Write summary metadata JSON alongside CSV",
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

    report = run_batch_validation(
        db_path,
        input_path,
        batch_id=args.batch_id,
        dry_run=args.dry_run,
    )
    print(format_batch_summary(report))

    if args.csv is not None:
        csv_path = (
            _default_csv_path(input_path, args.batch_id)
            if args.csv == "auto"
            else Path(args.csv)
        )
        write_batch_csv(report, csv_path)
        print(f"\nWrote CSV: {csv_path}")

    if args.meta or args.csv is not None:
        meta_path = DEFAULT_IMPORTS_DIR / f"{report.batch_id}.meta.json"
        write_batch_meta(report, meta_path)
        print(f"Wrote meta: {meta_path}")

    return 1 if report.summary.errors and report.summary.processed == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
