"""Tests for CFPB trademark scoring."""

from __future__ import annotations

from collectors.scoring.cfpb_trademark_score import score_band, score_candidate, score_entity


def test_score_entity_high_volume_multi_state() -> None:
    score = score_entity(
        complaint_count=20,
        state_count=5,
        products=["Payday loan, title loan, or personal loan"],
        narrative_count=10,
        last_seen_at="2026-01-15T00:00:00Z",
        normalized_name="cashnetusa",
    )
    assert score >= 70


def test_score_entity_generic_penalty() -> None:
    generic = score_entity(
        complaint_count=10,
        state_count=3,
        products=["Debt collection"],
        narrative_count=2,
        last_seen_at="2026-01-15T00:00:00Z",
        normalized_name="loan debt credit services",
    )
    specific = score_entity(
        complaint_count=10,
        state_count=3,
        products=["Debt collection"],
        narrative_count=2,
        last_seen_at="2026-01-15T00:00:00Z",
        normalized_name="acme funding group",
    )
    assert specific > generic


def test_score_candidate_company_field_bonus() -> None:
    company = score_candidate(
        entity_score=60,
        candidate_type="company_name",
        from_narrative=False,
        has_domain=False,
        complaint_count=5,
    )
    narrative = score_candidate(
        entity_score=60,
        candidate_type="possible_brand",
        from_narrative=True,
        has_domain=False,
        complaint_count=5,
    )
    assert company > narrative


def test_score_bands() -> None:
    assert score_band(90) == "strong"
    assert score_band(75) == "good"
    assert score_band(55) == "review"
    assert score_band(35) == "weak"
    assert score_band(10) == "reject"
