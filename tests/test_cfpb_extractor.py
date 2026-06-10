"""Tests for CFPB brand candidate extraction."""

from __future__ import annotations

from collectors.extractors.brand_candidate_extractor import extract_from_company, extract_from_narrative


def test_extract_from_company_field() -> None:
    candidates = extract_from_company("CASHNETUSA")
    assert len(candidates) >= 1
    assert candidates[0].normalized_candidate == "cashnetusa"
    assert candidates[0].candidate_type == "company_name"


def test_reject_generic_narrative_words() -> None:
    candidates = extract_from_narrative("I contacted the company about my loan")
    names = {c.normalized_candidate for c in candidates}
    assert "loan" not in names
    assert "the company" not in names


def test_extract_domain_from_narrative() -> None:
    candidates = extract_from_narrative("I applied at www.example-loans.com for help")
    assert any(c.candidate_type == "domain" for c in candidates)


def test_extract_trigger_phrase() -> None:
    candidates = extract_from_narrative("I applied with CashNetUSA for a personal loan")
    assert any("cashnetusa" in c.normalized_candidate for c in candidates)
