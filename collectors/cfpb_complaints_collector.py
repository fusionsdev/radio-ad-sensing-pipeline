"""CFPB Consumer Complaint Trademark Collector orchestrator."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from collectors.auto_approve import review_status_for_score, verification_status_for_score
from collectors.bridges.trademark_bridge import upsert_trademark_from_entity
from collectors.cfpb_api_client import fetch_complaints
from collectors.cfpb_csv_reader import stream_complaints_csv
from collectors.extractors.brand_candidate_extractor import (
    BrandCandidate,
    extract_from_company,
    extract_from_narrative,
)
from collectors.normalizers.company_name_normalizer import normalize_company_name
from collectors.scoring.cfpb_trademark_score import score_candidate, score_entity
from shared.config import load_cfpb_collector, load_settings, load_trademark_settings
from shared.db import get_connection, transaction
from shared.models import CfpbCollectorSettings

logger = logging.getLogger(__name__)

INSERT_RAW_SQL = """
INSERT OR IGNORE INTO cfpb_complaints_raw (
    complaint_id, date_received, product, sub_product, issue, sub_issue,
    consumer_complaint_narrative, company_public_response, company, state,
    zip_code, tags, consumer_consent_provided, submitted_via,
    date_sent_to_company, company_response_to_consumer, timely_response,
    consumer_disputed, raw_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iter_source_records(config: CfpbCollectorSettings) -> Iterator[dict[str, object]]:
    remaining = config.max_records_per_run
    per_combo = max(1, remaining // max(1, len(config.target_states) * len(config.target_products)))

    if config.source_mode == "bulk_csv":
        if not config.bulk_csv_path:
            raise ValueError("bulk_csv_path required when source_mode is bulk_csv")
        csv_path = Path(config.bulk_csv_path)
        yield from stream_complaints_csv(
            csv_path,
            target_states=config.target_states,
            target_products=config.target_products,
            date_from=config.date_from,
            date_to=config.date_to,
            max_records=config.max_records_per_run,
        )
        return

    for state in config.target_states:
        for product in config.target_products:
            yield from fetch_complaints(
                state=state,
                product=product,
                date_received_min=config.date_from,
                date_received_max=config.date_to,
                page_size=min(100, config.batch_size),
                max_records=per_combo,
                rate_limit_sleep=config.rate_limit_sleep_seconds,
                has_narrative=True if config.include_narratives else None,
            )


def insert_raw_batch(conn: sqlite3.Connection, records: list[dict[str, object]]) -> int:
    inserted = 0
    for record in records:
        cursor = conn.execute(
            INSERT_RAW_SQL,
            (
                record.get("complaint_id"),
                record.get("date_received"),
                record.get("product"),
                record.get("sub_product"),
                record.get("issue"),
                record.get("sub_issue"),
                record.get("consumer_complaint_narrative"),
                record.get("company_public_response"),
                record.get("company"),
                record.get("state"),
                record.get("zip_code"),
                record.get("tags"),
                record.get("consumer_consent_provided"),
                record.get("submitted_via"),
                record.get("date_sent_to_company"),
                record.get("company_response_to_consumer"),
                record.get("timely_response"),
                record.get("consumer_disputed"),
                record.get("raw_json"),
            ),
        )
        if cursor.rowcount > 0:
            inserted += 1
    return inserted


def aggregate_entities(
    conn: sqlite3.Connection,
    min_complaint_count: int,
    *,
    include_narratives: bool = True,
    config: CfpbCollectorSettings | None = None,
) -> int:
    rows = conn.execute(
        """
        SELECT company, product, state, date_received,
               consumer_complaint_narrative, complaint_id
        FROM cfpb_complaints_raw
        WHERE company IS NOT NULL AND TRIM(company) != ''
        """
    ).fetchall()

    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        company_raw = str(row["company"]).strip()
        normalized = normalize_company_name(company_raw)
        if not normalized:
            continue
        bucket = grouped.setdefault(
            normalized,
            {
                "company_raw": company_raw,
                "products": set(),
                "states": set(),
                "complaint_count": 0,
                "narrative_count": 0,
                "first_seen": None,
                "last_seen": None,
                "complaints": [],
            },
        )
        bucket["complaint_count"] = int(bucket["complaint_count"]) + 1
        if row["product"]:
            bucket["products"].add(str(row["product"]))
        if row["state"]:
            bucket["states"].add(str(row["state"]).upper())
        date_received = row["date_received"]
        if date_received:
            if bucket["first_seen"] is None or str(date_received) < str(bucket["first_seen"]):
                bucket["first_seen"] = str(date_received)
            if bucket["last_seen"] is None or str(date_received) > str(bucket["last_seen"]):
                bucket["last_seen"] = str(date_received)
        narrative = row["consumer_complaint_narrative"]
        if narrative and str(narrative).strip():
            bucket["narrative_count"] = int(bucket["narrative_count"]) + 1
        bucket["complaints"].append(
            {
                "complaint_id": row["complaint_id"],
                "company": company_raw,
                "product": row["product"],
                "state": row["state"],
                "narrative": narrative,
            }
        )

    entities_created = 0
    now = _now_iso()
    for normalized, data in grouped.items():
        if int(data["complaint_count"]) < min_complaint_count:
            continue
        products = sorted(data["products"])
        states = sorted(data["states"])
        entity_score = score_entity(
            complaint_count=int(data["complaint_count"]),
            state_count=len(states),
            products=products,
            narrative_count=int(data["narrative_count"]),
            last_seen_at=data["last_seen"],
            normalized_name=normalized,
        )
        entity_review = "new"
        if config:
            entity_review = review_status_for_score(
                entity_score,
                enabled=config.auto_approve_enabled,
                min_score=config.auto_approve_min_score,
            )
        existing = conn.execute(
            "SELECT id FROM cfpb_company_entities WHERE company_normalized = ?",
            (normalized,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE cfpb_company_entities SET
                    company_raw = ?, product_mix_json = ?, states_json = ?,
                    complaint_count = ?, narrative_count = ?,
                    first_seen_at = ?, last_seen_at = ?,
                    trademark_candidate_score = ?, review_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    data["company_raw"],
                    json.dumps(products),
                    json.dumps(states),
                    data["complaint_count"],
                    data["narrative_count"],
                    data["first_seen"],
                    data["last_seen"],
                    entity_score,
                    entity_review,
                    now,
                    existing[0],
                ),
            )
            entity_id = int(existing[0])
        else:
            cursor = conn.execute(
                """
                INSERT INTO cfpb_company_entities (
                    company_raw, company_normalized, product_mix_json, states_json,
                    complaint_count, narrative_count, first_seen_at, last_seen_at,
                    trademark_candidate_score, review_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["company_raw"],
                    normalized,
                    json.dumps(products),
                    json.dumps(states),
                    data["complaint_count"],
                    data["narrative_count"],
                    data["first_seen"],
                    data["last_seen"],
                    entity_score,
                    entity_review,
                    now,
                    now,
                ),
            )
            entity_id = int(cursor.lastrowid)
            entities_created += 1

        _refresh_candidates_for_entity(
            conn,
            entity_id=entity_id,
            entity_score=entity_score,
            complaints=list(data["complaints"]),
            include_narratives=include_narratives,
            complaint_count=int(data["complaint_count"]),
            config=config,
        )
    return entities_created


def _refresh_candidates_for_entity(
    conn: sqlite3.Connection,
    *,
    entity_id: int,
    entity_score: float,
    complaints: list[dict[str, object]],
    include_narratives: bool,
    complaint_count: int,
    config: CfpbCollectorSettings | None = None,
) -> int:
    conn.execute(
        "DELETE FROM cfpb_brand_candidates WHERE cfpb_company_entity_id = ?",
        (entity_id,),
    )
    seen: set[tuple[str, str]] = set()
    created = 0
    for complaint in complaints:
        company = str(complaint.get("company") or "")
        product = complaint.get("product")
        state = complaint.get("state")
        complaint_id = complaint.get("complaint_id")
        candidates: list[BrandCandidate] = extract_from_company(company)
        if include_narratives:
            narrative = complaint.get("narrative")
            if narrative:
                candidates.extend(extract_from_narrative(str(narrative)))

        for candidate in candidates:
            key = (candidate.normalized_candidate, candidate.candidate_type)
            if key in seen:
                continue
            seen.add(key)
            cand_score = score_candidate(
                entity_score=entity_score,
                candidate_type=candidate.candidate_type,
                from_narrative=candidate.candidate_type
                in {"possible_brand", "domain", "lender"},
                has_domain=candidate.candidate_type == "domain",
                complaint_count=complaint_count,
            )
            verify_status = "needs_verification"
            if config:
                verify_status = verification_status_for_score(
                    cand_score,
                    enabled=config.auto_approve_enabled,
                    min_score=config.auto_approve_min_score,
                    candidate_type=candidate.candidate_type,
                )
            conn.execute(
                """
                INSERT INTO cfpb_brand_candidates (
                    cfpb_company_entity_id, candidate_name, normalized_candidate,
                    candidate_type, source_product, source_state, source_complaint_id,
                    evidence_text, confidence, score, verification_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    candidate.candidate_name,
                    candidate.normalized_candidate,
                    candidate.candidate_type,
                    product,
                    state,
                    complaint_id,
                    candidate.evidence_text,
                    min(cand_score / 100.0, 1.0),
                    cand_score,
                    verify_status,
                ),
            )
            created += 1
    return created


def bridge_strong_entities(conn: sqlite3.Connection, config: CfpbCollectorSettings) -> int:
    if not config.output_to_trademark_layer:
        return 0
    tm_settings = load_trademark_settings()
    rows = conn.execute(
        """
        SELECT id, company_raw, company_normalized, trademark_candidate_score
        FROM cfpb_company_entities
        WHERE trademark_candidate_score >= ?
        """,
        (tm_settings.min_bridge_score,),
    ).fetchall()
    bridged = 0
    for row in rows:
        result = upsert_trademark_from_entity(
            conn,
            entity_id=int(row["id"]),
            company_raw=str(row["company_raw"]),
            company_normalized=str(row["company_normalized"]),
            trademark_score=float(row["trademark_candidate_score"]),
            settings=tm_settings,
            auto_approve=config.auto_approve_enabled,
            auto_approve_min_score=config.auto_approve_min_score,
        )
        if result is not None:
            bridged += 1
    return bridged


class CfpbComplaintsCollector:
    def __init__(self, db_path: Path, config: CfpbCollectorSettings) -> None:
        self.db_path = db_path
        self.config = config

    def run(self) -> dict[str, int]:
        if not self.config.enabled:
            logger.info("CFPB collector disabled in config")
            return {"status": "disabled"}

        conn = get_connection(self.db_path)
        run_id: int | None = None
        stats = defaultdict(int)
        try:
            started = _now_iso()
            cursor = conn.execute(
                """
                INSERT INTO cfpb_collection_runs (
                    started_at, source_mode, date_from, date_to,
                    target_states_json, target_products_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    started,
                    self.config.source_mode,
                    self.config.date_from,
                    self.config.date_to,
                    json.dumps(self.config.target_states),
                    json.dumps(self.config.target_products),
                ),
            )
            conn.commit()
            run_id = int(cursor.lastrowid)

            batch: list[dict[str, object]] = []
            for record in _iter_source_records(self.config):
                stats["records_seen"] += 1
                batch.append(record)
                if len(batch) >= self.config.batch_size:
                    with transaction(conn):
                        stats["records_inserted"] += insert_raw_batch(conn, batch)
                    batch.clear()

            if batch:
                with transaction(conn):
                    stats["records_inserted"] += insert_raw_batch(conn, batch)

            with transaction(conn):
                stats["entities_created"] = aggregate_entities(
                    conn,
                    self.config.min_company_complaint_count,
                    include_narratives=self.config.include_narratives,
                    config=self.config,
                )
                candidate_count = conn.execute("SELECT COUNT(*) FROM cfpb_brand_candidates").fetchone()
                stats["candidates_created"] = int(candidate_count[0]) if candidate_count else 0
                if self.config.output_to_trademark_layer:
                    stats["trademark_bridged"] = bridge_strong_entities(conn, self.config)

            conn.execute(
                """
                UPDATE cfpb_collection_runs SET
                    finished_at = ?, records_seen = ?, records_inserted = ?,
                    entities_created = ?, candidates_created = ?, status = 'completed'
                WHERE id = ?
                """,
                (
                    _now_iso(),
                    stats["records_seen"],
                    stats["records_inserted"],
                    stats["entities_created"],
                    stats["candidates_created"],
                    run_id,
                ),
            )
            conn.commit()
            stats["status"] = "completed"
            return dict(stats)
        except Exception as exc:
            logger.exception("CFPB collection failed")
            if run_id is not None:
                conn.execute(
                    """
                    UPDATE cfpb_collection_runs SET
                        finished_at = ?, status = 'failed', error_message = ?
                    WHERE id = ?
                    """,
                    (_now_iso(), str(exc), run_id),
                )
                conn.commit()
            raise
        finally:
            conn.close()


def run_collector(db_path: Path | None = None, config_path: Path | None = None) -> dict[str, int]:
    settings = load_settings()
    config = load_cfpb_collector(config_path)
    resolved_db = db_path or (Path(__file__).resolve().parent.parent / settings.db_path)
    collector = CfpbComplaintsCollector(resolved_db.resolve(), config)
    return collector.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="CFPB complaint trademark collector")
    parser.add_argument("--config", type=Path, default=None, help="Path to cfpb_collector.yaml")
    parser.add_argument("--db", type=Path, default=None, help="SQLite database path")
    args = parser.parse_args()
    result = run_collector(db_path=args.db, config_path=args.config)
    logger.info("CFPB collection finished: %s", result)


if __name__ == "__main__":
    main()
