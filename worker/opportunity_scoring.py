"""Opportunity scoring for novelty-first keyword discovery."""

from __future__ import annotations

from dataclasses import dataclass

SUPPRESSED_STATUSES = frozenset(
    {
        "known_duplicate",
        "near_duplicate",
        "generic",
        "excluded_vertical",
        "weak_evidence",
        "noise",
    }
)


@dataclass(frozen=True)
class OpportunityScoreInput:
    normalized_text: str
    vertical: str | None
    novelty_status: str
    source_confidence: float
    extraction_confidence: float
    word_count: int


def calculate_opportunity_score(payload: OpportunityScoreInput) -> float:
    """Score how actionable a candidate is for outbound reporting (0–100)."""
    if payload.novelty_status in SUPPRESSED_STATUSES:
        return max(0.0, min(40.0, payload.source_confidence * 30.0))

    score = 45.0

    if payload.word_count >= 5:
        score += 25.0
    elif payload.word_count >= 4:
        score += 20.0
    elif payload.word_count >= 3:
        score += 12.0
    elif payload.word_count <= 1:
        score -= 15.0

    score += payload.source_confidence * 25.0
    score += payload.extraction_confidence * 10.0

    if payload.vertical:
        score += 5.0

    return round(max(0.0, min(100.0, score)), 2)


def suggest_action(opportunity_score: float, vertical: str | None) -> str:
    if opportunity_score >= 85:
        return "prioritize_keyword_research"
    if opportunity_score >= 70:
        return "add_to_watchlist"
    if vertical:
        return "dashboard_review"
    return "monitor"
