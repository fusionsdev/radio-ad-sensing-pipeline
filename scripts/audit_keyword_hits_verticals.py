#!/usr/bin/env python3
"""Audit legacy keyword_hits for pre-consumer_personal_loan pollution (dry-run by default)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.db import get_connection, transaction
from shared.keyword_hits_audit import apply_keyword_hits_cleanup, audit_keyword_hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit keyword_hits for legacy vertical pollution.",
    )
    parser.add_argument(
        "--db",
        default="data/pipeline.db",
        help="SQLite database path (default: data/pipeline.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete flagged polluted keyword_hits rows (default: dry-run only)",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    conn = get_connection(db_path)
    try:
        report = audit_keyword_hits(conn)
        for line in report.summary_lines():
            print(line)

        deleted = 0
        if report.polluted_row_count > 0:
            print("")
            if args.apply:
                with transaction(conn):
                    deleted, messages = apply_keyword_hits_cleanup(
                        conn, report, apply=True
                    )
            else:
                _, messages = apply_keyword_hits_cleanup(conn, report, apply=False)
            for msg in messages:
                print(msg)

        if report.polluted_row_count and not args.apply:
            print("")
            print("Re-run with --apply to delete flagged rows after operator review.")

        return 0 if report.polluted_row_count == 0 or args.apply else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
