"""Tests for manual discovery candidate import."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from shared.db import get_connection, migrate
from worker.discovery_import import (
    import_discovery_candidates,
    import_discovery_candidates_file,
    load_candidates_json,
    validate_record,
)
from worker.novelty_engine import load_novelty_config


@pytest.fixture
def novelty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "import.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def sample_path() -> Path:
    return Path(__file__).resolve().parent.parent / "examples" / "discovery_candidates.sample.json"


def test_load_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    parsed = load_candidates_json(bad)
    assert parsed.records == []
    assert any("Invalid JSON" in err for err in parsed.errors)


def test_load_non_array_json(tmp_path: Path) -> None:
    bad = tmp_path / "object.json"
    bad.write_text('{"candidate_text": "x"}', encoding="utf-8")
    parsed = load_candidates_json(bad)
    assert parsed.records == []
    assert "top-level array" in parsed.errors[0]


def test_missing_required_fields() -> None:
    errors = validate_record({"candidate_text": "only text"}, index=0)
    assert any("candidate_type" in err for err in errors)
    assert any("vertical" in err for err in errors)


def test_importer_dry_run(sample_path: Path, novelty_db: Path) -> None:
    summary = import_discovery_candidates_file(novelty_db, sample_path, dry_run=True)
    assert summary.total_input == 6
    assert summary.processed == 6
    assert summary.report_eligible == 2
    assert summary.suppressed_known >= 1
    assert summary.suppressed_generic >= 1
    assert summary.suppressed_excluded >= 1

    conn = get_connection(novelty_db)
    try:
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_discovery_items").fetchone()[0]
        opp_count = conn.execute("SELECT COUNT(*) FROM keyword_opportunities").fetchone()[0]
    finally:
        conn.close()
    assert raw_count == 0
    assert opp_count == 0


def test_importer_db_write(novelty_db: Path) -> None:
    records = [
        {
            "candidate_text": "dog ACL surgery payment plan",
            "candidate_type": "use_case",
            "vertical": "pet_financing",
            "source_type": "reddit",
            "source_url": "https://example.com/thread/1",
            "evidence_text": "Vet quoted $4,800 for ACL surgery.",
            "source_confidence": 0.85,
        },
        {
            "candidate_text": "CareCredit",
            "candidate_type": "brand",
            "vertical": "medical_financing",
            "source_type": "serp",
            "source_url": "https://example.com/carecredit",
            "evidence_text": "CareCredit ad snippet.",
            "source_confidence": 0.90,
        },
    ]
    summary = import_discovery_candidates(novelty_db, records, config=load_novelty_config())
    assert summary.processed == 2
    assert summary.report_eligible == 1
    assert summary.suppressed_known == 1

    conn = get_connection(novelty_db)
    try:
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_discovery_items").fetchone()[0]
        candidate_count = conn.execute("SELECT COUNT(*) FROM candidate_terms").fetchone()[0]
        novelty_count = conn.execute("SELECT COUNT(*) FROM novelty_results").fetchone()[0]
        opp_count = conn.execute("SELECT COUNT(*) FROM keyword_opportunities").fetchone()[0]
        linked = conn.execute(
            """
            SELECT COUNT(*) FROM candidate_terms ct
            JOIN raw_discovery_items r ON r.id = ct.raw_item_id
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert raw_count == 2
    assert candidate_count == 2
    assert novelty_count == 2
    assert opp_count == 1
    assert linked == 2


def test_sample_json_processing(novelty_db: Path, sample_path: Path) -> None:
    summary = import_discovery_candidates_file(novelty_db, sample_path, dry_run=False)
    assert summary.total_input == 6
    assert summary.processed == 6
    assert summary.report_eligible == 2

    conn = get_connection(novelty_db)
    try:
        opp_texts = {
            row[0]
            for row in conn.execute(
                "SELECT opportunity_text FROM keyword_opportunities"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "dog ACL surgery payment plan" in opp_texts
    assert "root canal payment plan no upfront" in opp_texts
    assert "CareCredit" not in opp_texts
    assert "pet financing" not in opp_texts


def test_digest_preview_route(novelty_db: Path) -> None:
    import_discovery_candidates(
        novelty_db,
        [
            {
                "candidate_text": "dog ACL surgery payment plan",
                "candidate_type": "use_case",
                "vertical": "pet_financing",
                "source_type": "manual",
                "source_url": "https://example.com/1",
                "evidence_text": "Payment plan discussion",
                "source_confidence": 0.85,
            }
        ],
    )
    client = TestClient(create_app(db_path=novelty_db))
    response = client.get("/opportunities/digest-preview")
    assert response.status_code == 200
    assert "dog ACL surgery payment plan" in response.text
    assert "dry-run" in response.text.lower() or "Dry-run" in response.text


def test_import_script_dry_run_cli(sample_path: Path, novelty_db: Path, capsys) -> None:
    from scripts.import_discovery_candidates import main

    rc = main(["--db", str(novelty_db), "--input", str(sample_path), "--dry-run"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "DRY RUN" in captured
    assert "Report eligible:" in captured
