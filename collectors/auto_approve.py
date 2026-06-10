"""Auto-approve helpers for high-confidence CFPB seeds (opt-in via config)."""

from __future__ import annotations

# Narrative/domain extractions stay manual review even when auto-approve is on.
AUTO_APPROVE_EXCLUDED_TYPES = frozenset({"possible_brand", "domain", "unknown"})


def should_auto_approve(
    score: float,
    *,
    enabled: bool,
    min_score: float,
    candidate_type: str | None = None,
) -> bool:
    if not enabled or score < min_score:
        return False
    if candidate_type and candidate_type in AUTO_APPROVE_EXCLUDED_TYPES:
        return False
    return True


def verification_status_for_score(
    score: float,
    *,
    enabled: bool,
    min_score: float,
    candidate_type: str | None = None,
) -> str:
    if should_auto_approve(
        score, enabled=enabled, min_score=min_score, candidate_type=candidate_type
    ):
        return "approved_seed"
    return "needs_verification"


def review_status_for_score(score: float, *, enabled: bool, min_score: float) -> str:
    if should_auto_approve(score, enabled=enabled, min_score=min_score):
        return "approved_seed"
    return "new"
