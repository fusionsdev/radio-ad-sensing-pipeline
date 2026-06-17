"""Aggregate CFPB raw complaints already in DB (skip API fetch)."""
from __future__ import annotations

from pathlib import Path

from collectors.cfpb_complaints_collector import aggregate_entities, bridge_strong_entities
from shared.config import load_cfpb_collector
from shared.db import get_connection, transaction


def main() -> None:
    config = load_cfpb_collector(Path("/app/config/cfpb_collector.yaml"))
    conn = get_connection("/app/data/pipeline.db")
    try:
        raw = conn.execute("SELECT COUNT(*) FROM cfpb_complaints_raw").fetchone()[0]
        print(f"raw_complaints={raw}")
        with transaction(conn):
            entities = aggregate_entities(
                conn,
                config.min_company_complaint_count,
                include_narratives=config.include_narratives,
                config=config,
            )
            bridged = (
                bridge_strong_entities(conn, config)
                if config.output_to_trademark_layer
                else 0
            )
        candidates = conn.execute("SELECT COUNT(*) FROM cfpb_brand_candidates").fetchone()[0]
        conn.execute(
            """
            UPDATE cfpb_collection_runs SET
                status = 'completed',
                finished_at = datetime('now'),
                records_seen = ?,
                records_inserted = ?,
                entities_created = ?,
                candidates_created = ?
            WHERE id = (SELECT MAX(id) FROM cfpb_collection_runs)
            """,
            (raw, raw, entities, candidates),
        )
        conn.commit()
        print(f"entities={entities} candidates={candidates} bridged={bridged}")
        print("integrity", conn.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
