"""Export brand candidates from standalone CFPB DB to CSV."""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "cfpb_standalone.db"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "cfpb_candidates_standalone.csv"

QUERY = """
SELECT c.id, c.candidate_name, c.normalized_candidate, c.candidate_type,
       c.score, c.verification_status, c.source_product, c.source_state,
       e.company_raw, e.complaint_count, e.trademark_candidate_score
FROM cfpb_brand_candidates c
LEFT JOIN cfpb_company_entities e ON e.id = c.cfpb_company_entity_id
WHERE c.score >= ?
ORDER BY c.score DESC, c.id DESC
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--min-score", type=float, default=70.0)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(QUERY, (args.min_score,)).fetchall()
    conn.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print(f"No rows at min_score>={args.min_score} in {args.db}")
        return

    fieldnames = list(rows[0].keys())
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([dict(row) for row in rows])

    print(f"Wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
