"""Tests for CFPB auto-approve (opt-in, score-gated)."""

from __future__ import annotations

from collectors.auto_approve import (
    review_status_for_score,
    verification_status_for_score,
)


def test_auto_approve_off_by_default() -> None:
    assert verification_status_for_score(90, enabled=False, min_score=85) == "needs_verification"
    assert review_status_for_score(90, enabled=False, min_score=85) == "new"


def test_auto_approve_high_score_company_name() -> None:
    assert (
        verification_status_for_score(
            90, enabled=True, min_score=85, candidate_type="company_name"
        )
        == "approved_seed"
    )
    assert review_status_for_score(90, enabled=True, min_score=85) == "approved_seed"


def test_auto_approve_skips_narrative_types() -> None:
    assert (
        verification_status_for_score(
            90, enabled=True, min_score=85, candidate_type="possible_brand"
        )
        == "needs_verification"
    )
    assert (
        verification_status_for_score(90, enabled=True, min_score=85, candidate_type="domain")
        == "needs_verification"
    )


def test_auto_approve_below_threshold() -> None:
    assert verification_status_for_score(70, enabled=True, min_score=85) == "needs_verification"
