"""Tests for CFPB collector ingestion and aggregation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from collectors.cfpb_api_client import parse_complaint_record
from collectors.cfpb_complaints_collector import (
    CfpbComplaintsCollector,
    aggregate_entities,
    insert_raw_batch,
)
from collectors.cfpb_csv_reader import stream_complaints_csv
from shared.db import get_connection, migrate
from shared.models import CfpbCollectorSettings


SAMPLE_API_SOURCE = {
    "complaint_id": 12345,
    "date_received": "2024-06-01",
    "product": "Payday loan, title loan, or personal loan",
    "company": "ENOVA INTERNATIONAL, INC.",
    "state": "TX",
    "consumer_complaint_narrative": "I applied with CashNetUSA for a loan",
}


def test_parse_complaint_record() -> None:
    record = parse_complaint_record(SAMPLE_API_SOURCE)
    assert record["complaint_id"] == "12345"
    assert record["company"] == "ENOVA INTERNATIONAL, INC."
    assert record["state"] == "TX"
    assert json.loads(record["raw_json"])["complaint_id"] == 12345


def test_insert_raw_dedup(tmp_path: Path) -> None:
    db_path = tmp_path / "raw.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        record = parse_complaint_record(SAMPLE_API_SOURCE)
        first = insert_raw_batch(conn, [record])
        conn.commit()
        second = insert_raw_batch(conn, [record])
        conn.commit()
        assert first == 1
        assert second == 0
    finally:
        conn.close()


def test_aggregate_entities_min_count(tmp_path: Path) -> None:
    db_path = tmp_path / "agg.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        for idx in range(3):
            conn.execute(
                """
                INSERT INTO cfpb_complaints_raw (
                    complaint_id, date_received, product, company, state, raw_json
                ) VALUES (?, '2024-01-01', 'Debt collection', 'Acme Collections LLC', 'TX', '{}')
                """,
                (f"c-{idx}",),
            )
        conn.commit()
        created = aggregate_entities(conn, min_complaint_count=3, include_narratives=False)
        conn.commit()
        assert created == 1
        row = conn.execute(
            "SELECT complaint_count, company_normalized FROM cfpb_company_entities"
        ).fetchone()
        assert row["complaint_count"] == 3
        assert row["company_normalized"] == "acme collections"
    finally:
        conn.close()


def test_csv_stream_filter(tmp_path: Path) -> None:
    csv_path = tmp_path / "complaints.csv"
    csv_path.write_text(
        "complaint_id,date_received,product,company,state\n"
        "1,2024-01-01,Debt collection,Acme LLC,TX\n"
        "2,2024-01-01,Credit card,Other Bank,NY\n"
        "3,2023-01-01,Debt collection,Old Co,TX\n",
        encoding="utf-8",
    )
    records = list(
        stream_complaints_csv(
            csv_path,
            target_states=["TX"],
            target_products=["Debt collection"],
            date_from="2024-01-01",
            max_records=10,
        )
    )
    assert len(records) == 1
    assert records[0]["complaint_id"] == "1"


def test_collector_run_api_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "run.db"
    migrate(db_path)
    config = CfpbCollectorSettings(
        enabled=True,
        source_mode="api",
        target_states=["TX"],
        target_products=["Debt collection"],
        date_from="2024-01-01",
        batch_size=10,
        max_records_per_run=5,
        rate_limit_sleep_seconds=0,
        include_narratives=False,
        min_company_complaint_count=1,
        output_to_trademark_layer=True,
    )
    fake_records = [
        parse_complaint_record(
            {
                **SAMPLE_API_SOURCE,
                "complaint_id": idx,
                "product": "Debt collection",
                "company": "Acme Collections LLC",
            }
        )
        for idx in range(3)
    ]

    def fake_iter(_config: CfpbCollectorSettings):
        yield from fake_records

    with patch("collectors.cfpb_complaints_collector._iter_source_records", fake_iter):
        result = CfpbComplaintsCollector(db_path, config).run()

    assert result["status"] == "completed"
    assert result["records_inserted"] == 3
    conn = get_connection(db_path, read_only=True)
    try:
        entities = conn.execute("SELECT COUNT(*) FROM cfpb_company_entities").fetchone()[0]
        runs = conn.execute("SELECT status FROM cfpb_collection_runs").fetchone()
        assert entities >= 1
        assert runs["status"] == "completed"
    finally:
        conn.close()
