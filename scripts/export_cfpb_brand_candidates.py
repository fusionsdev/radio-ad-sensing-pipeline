#!/usr/bin/env python3
"""Export CFPB brand candidates to CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from shared.config import load_settings
from shared.db import get_connection, migrate


def export_candidates(db_path: Path, output_path: Path, *, min_score: float | None = None) -> int:
    conn = get_connection(db_path, read_only=True)
    try:
        clauses = ["1=1"]
        params: list[object] = []
        if min_score is not None:
            clauses.append("c.score >= ?")
            params.append(min_score)
        sql = f"""
            SELECT c.candidate_name, c.normalized_candidate, c.candidate_type,
                   c.score, c.confidence, e.complaint_count, e.states_json,
                   e.product_mix_json, e.first_seen_at, e.last_seen_at,
                   c.verification_status, e.notes
            FROM cfpb_brand_candidates c
            LEFT JOIN cfpb_company_entities e ON e.id = c.cfpb_company_entity_id
            WHERE {" AND ".join(clauses)}
            ORDER BY c.score DESC, c.id
        """
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_name",
                "normalized_candidate",
                "candidate_type",
                "score",
                "confidence",
                "complaint_count",
                "states",
                "products",
                "first_seen_at",
                "last_seen_at",
                "verification_status",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            states = row["states_json"]
            products = row["product_mix_json"]
            writer.writerow(
                {
                    "candidate_name": row["candidate_name"],
                    "normalized_candidate": row["normalized_candidate"],
                    "candidate_type": row["candidate_type"],
                    "score": row["score"],
                    "confidence": row["confidence"],
                    "complaint_count": row["complaint_count"],
                    "states": ", ".join(json.loads(states)) if states else "",
                    "products": ", ".join(json.loads(products)) if products else "",
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "verification_status": row["verification_status"],
                    "notes": row["notes"],
                }
            )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CFPB brand candidates CSV")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("-o", "--output", type=Path, default=Path("data/cfpb_brand_candidates.csv"))
    parser.add_argument("--min-score", type=float, default=None)
    args = parser.parse_args()

    settings = load_settings()
    db_path = args.db or Path(settings.db_path)
    if not db_path.is_file():
        migrate(db_path)

    count = export_candidates(db_path.resolve(), args.output, min_score=args.min_score)
    print(f"Exported {count} candidates to {args.output}")


if __name__ == "__main__":
    main()
