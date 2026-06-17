"""Tests for novelty-first keyword discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alerter.novelty_reporter import format_pending_digest
from dashboard.main import create_app
from shared.db import get_connection, migrate
from worker.novelty_engine import (
    CandidateInput,
    evaluate_candidate,
    load_novelty_config,
    normalize_candidate_text,
    process_candidate,
)
from worker.opportunity_scoring import OpportunityScoreInput, calculate_opportunity_score


@pytest.fixture
def novelty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "novelty.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def config_paths(tmp_path: Path) -> dict[str, Path]:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    known_entities = config_dir / "known_entities.yaml"
    known_entities.write_text(
        """
known_brands:
  pet_financing:
    - carecredit
    - care credit
  personal_loan:
    - sofi
""",
        encoding="utf-8",
    )
    known_keywords = config_dir / "known_keywords.yaml"
    known_keywords.write_text(
        """
known_generic_keywords:
  - personal loan
  - pet financing
""",
        encoding="utf-8",
    )
    excluded = config_dir / "excluded_verticals.yaml"
    excluded.write_text(
        """
excluded_verticals:
  - title_loan
  - payday_loan
""",
        encoding="utf-8",
    )
    rules = config_dir / "novelty_rules.yaml"
    rules.write_text(
        """
thresholds:
  report_novelty_score: 75
  report_opportunity_score: 70
  min_source_confidence: 0.70
  dashboard_only_score: 40
  noise_score: 20
  near_duplicate_ratio: 85
reporting:
  report_known_brands: false
  report_known_keywords: false
  report_excluded_verticals: false
  require_evidence_text: true
  require_source_url: true
""",
        encoding="utf-8",
    )
    return {
        "known_entities": known_entities,
        "known_keywords": known_keywords,
        "excluded_verticals": excluded,
        "novelty_rules": rules,
    }


@pytest.fixture
def novelty_config(config_paths: dict[str, Path]):
    return load_novelty_config(
        known_entities_path=config_paths["known_entities"],
        known_keywords_path=config_paths["known_keywords"],
        excluded_verticals_path=config_paths["excluded_verticals"],
        novelty_rules_path=config_paths["novelty_rules"],
    )


def test_load_novelty_config(novelty_config) -> None:
    assert "carecredit" in novelty_config.known_brands
    assert "pet financing" in novelty_config.known_keywords
    assert "title_loan" in novelty_config.excluded_verticals
    assert novelty_config.rules.report_novelty_score == 75


def test_normalize_candidate_text() -> None:
    assert normalize_candidate_text("  CareCredit!!! ") == "carecredit"
    assert normalize_candidate_text("Dog   ACL   Surgery") == "dog acl surgery"


def test_exact_known_brand_suppression(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(candidate_text="CareCredit", vertical="medical_financing"),
        novelty_config,
    )
    assert result.novelty_status == "known_duplicate"
    assert result.report_eligible is False
    assert result.known_match_type == "brand"


def test_exact_known_keyword_suppression(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(candidate_text="pet financing", vertical="pet_financing"),
        novelty_config,
    )
    assert result.novelty_status == "generic"
    assert result.report_eligible is False


def test_excluded_vertical_suppression(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(candidate_text="title loan", vertical="title_loan"),
        novelty_config,
    )
    assert result.novelty_status == "excluded_vertical"
    assert result.report_eligible is False


def test_near_duplicate_suppression(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(candidate_text="care creditt", vertical="medical_financing"),
        novelty_config,
    )
    assert result.novelty_status == "near_duplicate"
    assert result.report_eligible is False
    assert result.similarity_score is not None
    assert result.similarity_score >= 85


def test_generic_keyword_suppression(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(candidate_text="personal loan", vertical="personal_loan"),
        novelty_config,
    )
    assert result.novelty_status == "generic"
    assert result.report_eligible is False


def test_report_eligible_new_use_case(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(
            candidate_text="dog ACL surgery payment plan",
            vertical="pet_financing",
            source_type="forum",
            source_url="https://example.com/pet-thread",
            evidence_text="Need help paying for ACL surgery for my dog.",
            source_confidence=0.85,
        ),
        novelty_config,
    )
    assert result.novelty_status in {"new", "needs_review"}
    assert result.novelty_score >= 75
    assert result.opportunity_score >= 70
    assert result.report_eligible is True


def test_report_eligible_dental_use_case(novelty_config) -> None:
    result = evaluate_candidate(
        CandidateInput(
            candidate_text="root canal payment plan no upfront",
            vertical="dental_financing",
            source_type="forum",
            source_url="https://example.com/dental-thread",
            evidence_text="Dentist offered monthly payments with no upfront cost.",
            source_confidence=0.80,
        ),
        novelty_config,
    )
    assert result.report_eligible is True


def test_opportunity_scoring() -> None:
    suppressed = calculate_opportunity_score(
        OpportunityScoreInput(
            normalized_text="pet financing",
            vertical="pet_financing",
            novelty_status="generic",
            source_confidence=0.9,
            extraction_confidence=0.5,
            word_count=2,
        )
    )
    assert suppressed <= 40

    strong = calculate_opportunity_score(
        OpportunityScoreInput(
            normalized_text="dog acl surgery payment plan",
            vertical="pet_financing",
            novelty_status="new",
            source_confidence=0.85,
            extraction_confidence=0.7,
            word_count=5,
        )
    )
    assert strong >= 70


def test_migration_creates_novelty_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    applied = migrate(db_path)
    assert 19 in applied
    conn = get_connection(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in (
            "raw_discovery_items",
            "candidate_terms",
            "novelty_results",
            "keyword_opportunities",
        ):
            assert table in tables
    finally:
        conn.close()


def test_process_candidate_persists_opportunity(novelty_db: Path, novelty_config) -> None:
    _, evaluation = process_candidate(
        novelty_db,
        CandidateInput(
            candidate_text="dog ACL surgery payment plan",
            vertical="pet_financing",
            source_type="manual",
            source_url="https://example.com/1",
            evidence_text="Payment plan discussion",
            source_confidence=0.85,
        ),
        config=novelty_config,
    )
    assert evaluation.report_eligible is True

    conn = get_connection(novelty_db)
    try:
        opp_count = conn.execute("SELECT COUNT(*) FROM keyword_opportunities").fetchone()[0]
        novelty_count = conn.execute("SELECT COUNT(*) FROM novelty_results").fetchone()[0]
    finally:
        conn.close()
    assert opp_count == 1
    assert novelty_count == 1


def test_known_brand_not_persisted_as_opportunity(novelty_db: Path, novelty_config) -> None:
    process_candidate(
        novelty_db,
        CandidateInput(candidate_text="CareCredit", vertical="medical_financing"),
        config=novelty_config,
    )
    conn = get_connection(novelty_db)
    try:
        opp_count = conn.execute("SELECT COUNT(*) FROM keyword_opportunities").fetchone()[0]
    finally:
        conn.close()
    assert opp_count == 0


def test_novelty_dashboard_routes_smoke(novelty_db: Path, novelty_config) -> None:
    process_candidate(
        novelty_db,
        CandidateInput(
            candidate_text="dog ACL surgery payment plan",
            vertical="pet_financing",
            source_url="https://example.com/x",
            evidence_text="evidence",
            source_confidence=0.85,
        ),
        config=novelty_config,
    )
    client = TestClient(create_app(db_path=novelty_db))
    for route in ("/novelty", "/novelty/new", "/novelty/known", "/novelty/noise", "/opportunities"):
        response = client.get(route)
        assert response.status_code == 200, route


def test_novelty_reporter_dry_run(novelty_db: Path, novelty_config) -> None:
    process_candidate(
        novelty_db,
        CandidateInput(
            candidate_text="dog ACL surgery payment plan",
            vertical="pet_financing",
            source_type="manual",
            source_url="https://example.com/1",
            evidence_text="Need payment help",
            source_confidence=0.85,
        ),
        config=novelty_config,
    )
    digest = format_pending_digest(novelty_db)
    assert "dog ACL surgery payment plan" in digest
