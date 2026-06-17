"""Tests for research batch validation workflow."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from shared.db import get_connection, migrate
from worker.batch_validation import (
    format_batch_summary,
    run_batch_validation,
    write_batch_csv,
)


@pytest.fixture
def novelty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "batch.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def batch_sample() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "imports"
        / "research_batch_001.sample.json"
    )


def test_batch_validation_summary(novelty_db: Path, batch_sample: Path) -> None:
    report = run_batch_validation(novelty_db, batch_sample, dry_run=True)
    assert report.batch_id == "research_batch_001"
    assert report.summary.total_input == 30
    assert report.summary.processed == 30
    assert report.summary.report_eligible >= 5
    assert report.status_counts.get("known_duplicate", 0) >= 3
    assert report.status_counts.get("generic", 0) >= 3
    assert report.status_counts.get("excluded_vertical", 0) >= 3
    assert report.suppression_counts
    assert sum(report.score_distribution.values()) == 30
    assert report.top_opportunities
    text = format_batch_summary(report)
    assert "Top opportunities:" in text
    assert "Suppressed reasons:" in text


def test_batch_validation_db_import(novelty_db: Path, batch_sample: Path) -> None:
    report = run_batch_validation(novelty_db, batch_sample, dry_run=False)
    assert report.summary.processed == 30

    conn = get_connection(novelty_db)
    try:
        batch_count = conn.execute(
            """
            SELECT COUNT(*) FROM raw_discovery_items
            WHERE json_extract(raw_json, '$.batch_id') = 'research_batch_001'
            """
        ).fetchone()[0]
        opp_count = conn.execute("SELECT COUNT(*) FROM keyword_opportunities").fetchone()[0]
    finally:
        conn.close()
    assert batch_count == 30
    assert opp_count == report.summary.report_eligible


def test_write_batch_csv(novelty_db: Path, batch_sample: Path, tmp_path: Path) -> None:
    report = run_batch_validation(novelty_db, batch_sample, dry_run=True)
    csv_path = tmp_path / "research_batch_001.results.csv"
    write_batch_csv(report, csv_path)
    assert csv_path.is_file()

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    assert rows[0]["batch_id"] == "research_batch_001"
    assert "novelty_status" in rows[0]
    assert "report_suppressed_reason" in rows[0]


def test_batch_review_dashboard_route(novelty_db: Path, batch_sample: Path) -> None:
    run_batch_validation(novelty_db, batch_sample, dry_run=False)
    client = TestClient(create_app(db_path=novelty_db))
    response = client.get("/opportunities/batch-review")
    assert response.status_code == 200
    assert "research_batch_001" in response.text
    assert "Suppressed reasons" in response.text
    assert "Top report-eligible opportunities" in response.text


def test_validate_research_batch_script(batch_sample: Path, novelty_db: Path, tmp_path: Path, capsys) -> None:
    from scripts.validate_research_batch import main

    csv_path = tmp_path / "out.results.csv"
    rc = main(
        [
            "--db",
            str(novelty_db),
            "--input",
            str(batch_sample),
            "--dry-run",
            "--csv",
            str(csv_path),
        ]
    )
    assert rc == 0
    assert csv_path.is_file()
    captured = capsys.readouterr().out
    assert "research_batch_001" in captured
    assert "Report eligible:" in captured
