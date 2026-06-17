"""Tests for landing page text importer."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from shared.db import get_connection, migrate
from worker.landing_page_import import (
    LandingPageSpec,
    extract_candidate_phrases,
    extract_visible_text,
    import_landing_pages,
    is_boilerplate_phrase,
    load_landing_pages_json,
    write_landing_pages_csv,
    write_landing_pages_meta,
)
from worker.novelty_engine import load_novelty_config


@pytest.fixture
def sample_html() -> str:
    return Path(__file__).resolve().parent.joinpath("fixtures", "landing_page_sample.html").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def novelty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "landing.db"
    migrate(db_path)
    return db_path


@pytest.fixture
def config_paths(tmp_path: Path) -> dict[str, Path]:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "known_entities.yaml").write_text(
        "known_brands:\n  pet_financing:\n    - carecredit\n",
        encoding="utf-8",
    )
    (config_dir / "known_keywords.yaml").write_text(
        "known_generic_keywords:\n  - pet financing\n",
        encoding="utf-8",
    )
    (config_dir / "excluded_verticals.yaml").write_text(
        "excluded_verticals:\n  - title_loan\n",
        encoding="utf-8",
    )
    (config_dir / "novelty_rules.yaml").write_text(
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
        "known_entities": config_dir / "known_entities.yaml",
        "known_keywords": config_dir / "known_keywords.yaml",
        "excluded_verticals": config_dir / "excluded_verticals.yaml",
        "novelty_rules": config_dir / "novelty_rules.yaml",
    }


@pytest.fixture
def novelty_config(config_paths: dict[str, Path]):
    return load_novelty_config(
        known_entities_path=config_paths["known_entities"],
        known_keywords_path=config_paths["known_keywords"],
        excluded_verticals_path=config_paths["excluded_verticals"],
        novelty_rules_path=config_paths["novelty_rules"],
    )


def test_extract_visible_text(sample_html: str) -> None:
    page = extract_visible_text(sample_html, url="https://example.com/vet-financing")
    assert page.title == "Emergency Vet Bill Payment Options | Example Vet Finance"
    assert "monthly payments" in page.meta_description
    assert any("dog acl surgery payment plan" in h.lower() for h in page.headings)
    assert "Apply Now" in page.cta_buttons
    assert "Privacy Policy" not in " ".join(page.headings)


def test_boilerplate_removal() -> None:
    assert is_boilerplate_phrase("Apply Now")
    assert is_boilerplate_phrase("Privacy Policy")
    assert not is_boilerplate_phrase("dog ACL surgery payment plan")


def test_candidate_phrase_extraction(sample_html: str) -> None:
    page = extract_visible_text(sample_html, url="https://example.com/vet-financing")
    phrases = extract_candidate_phrases(page)
    texts = {phrase.candidate_text.lower() for phrase in phrases}
    assert "dog acl surgery payment plan for unexpected vet bills" in texts
    assert "check eligibility without affecting credit" in texts
    assert "apply now" not in texts
    assert any("root canal payment plan" in text for text in texts)


def test_dry_run_import(sample_html: str, novelty_db: Path, novelty_config) -> None:
    report = import_landing_pages(
        novelty_db,
        [LandingPageSpec("https://example.com/vet-financing", "pet_financing", 0.85)],
        dry_run=True,
        fetch_fn=lambda url, timeout: (200, sample_html),
        config=novelty_config,
    )
    assert report.pages_processed == 1
    assert report.candidates_extracted >= 5
    assert report.candidates_processed == report.candidates_extracted
    assert report.report_eligible >= 1

    conn = get_connection(novelty_db)
    try:
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_discovery_items").fetchone()[0]
    finally:
        conn.close()
    assert raw_count == 0


def test_db_import(sample_html: str, novelty_db: Path, novelty_config) -> None:
    report = import_landing_pages(
        novelty_db,
        [LandingPageSpec("https://example.com/vet-financing", "pet_financing", 0.85)],
        fetch_fn=lambda url, timeout: (200, sample_html),
        config=novelty_config,
    )
    assert report.pages_processed == 1
    conn = get_connection(novelty_db)
    try:
        raw_count = conn.execute(
            "SELECT COUNT(*) FROM raw_discovery_items WHERE source_type = 'landing_page'"
        ).fetchone()[0]
        candidate_count = conn.execute(
            "SELECT COUNT(*) FROM candidate_terms WHERE source_type = 'landing_page'"
        ).fetchone()[0]
        opp_count = conn.execute("SELECT COUNT(*) FROM keyword_opportunities").fetchone()[0]
    finally:
        conn.close()
    assert raw_count == 1
    assert candidate_count == report.candidates_processed
    assert opp_count == report.report_eligible


def test_bad_url_handling(novelty_db: Path, novelty_config) -> None:
    def mock_fetch(url: str, timeout: float) -> tuple[int | None, str]:
        if "missing" in url:
            return 404, "not found"
        raise RuntimeError("network down")

    report = import_landing_pages(
        novelty_db,
        [
            LandingPageSpec("https://example.com/missing", "pet_financing", 0.8),
            LandingPageSpec("https://example.com/down", "pet_financing", 0.8),
        ],
        fetch_fn=mock_fetch,
        config=novelty_config,
    )
    assert report.pages_processed == 0
    assert len(report.errors) == 2


def test_csv_and_meta_output(sample_html: str, novelty_db: Path, novelty_config, tmp_path: Path) -> None:
    report = import_landing_pages(
        novelty_db,
        [LandingPageSpec("https://example.com/vet-financing", "pet_financing", 0.85)],
        dry_run=True,
        fetch_fn=lambda url, timeout: (200, sample_html),
        config=novelty_config,
    )
    csv_path = tmp_path / "landing_pages.results.csv"
    meta_path = tmp_path / "landing_pages.meta.json"
    write_landing_pages_csv(report, csv_path)
    write_landing_pages_meta(report, meta_path)
    assert csv_path.is_file()
    assert meta_path.is_file()
    assert "candidate_text" in csv_path.read_text(encoding="utf-8")
    assert "landing_pages_import" in meta_path.read_text(encoding="utf-8")


def test_load_landing_pages_json(tmp_path: Path) -> None:
    path = tmp_path / "pages.json"
    path.write_text(
        '[{"url":"https://example.com/x","vertical":"pet_financing","source_confidence":0.8}]',
        encoding="utf-8",
    )
    specs, errors = load_landing_pages_json(path)
    assert len(specs) == 1
    assert not errors
    assert specs[0].url.endswith("/x")


def test_dashboard_landing_pages_route(sample_html: str, novelty_db: Path, novelty_config) -> None:
    import_landing_pages(
        novelty_db,
        [LandingPageSpec("https://example.com/vet-financing", "pet_financing", 0.85)],
        fetch_fn=lambda url, timeout: (200, sample_html),
        config=novelty_config,
    )
    client = TestClient(create_app(db_path=novelty_db))
    response = client.get("/sources/landing-pages")
    assert response.status_code == 200
    assert "Landing page import results" in response.text
    assert "vet-financing" in response.text
