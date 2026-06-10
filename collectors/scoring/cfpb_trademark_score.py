"""Scoring CFPB company entities and brand candidates for trademark seed review."""

from __future__ import annotations

from datetime import UTC, datetime

HIGH_RELEVANCE_PRODUCTS = frozenset(
    {
        "payday loan, title loan, or personal loan",
        "debt collection",
        "debt settlement",
        "credit reporting or other personal consumer reports",
        "mortgage",
        "vehicle loan or lease",
    }
)

MEDIUM_RELEVANCE_PRODUCTS = frozenset(
    {
        "credit card",
        "checking or savings account",
        "money transfer, virtual currency, or money service",
    }
)

LOW_RELEVANCE_PRODUCTS = frozenset({"student loan"})

GENERIC_NAME_TOKENS = frozenset(
    {"loan", "debt", "credit", "bank", "financial", "services", "management", "solutions"}
)


def product_relevance_weight(product: str) -> float:
    key = product.strip().lower()
    if key in HIGH_RELEVANCE_PRODUCTS:
        return 1.0
    if key in MEDIUM_RELEVANCE_PRODUCTS:
        return 0.6
    if key in LOW_RELEVANCE_PRODUCTS:
        return 0.3
    return 0.5


def _recency_bonus(last_seen_at: str | None) -> float:
    if not last_seen_at:
        return 0.0
    try:
        seen = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - seen).days
        if age_days <= 90:
            return 10.0
        if age_days <= 365:
            return 5.0
        return 0.0
    except ValueError:
        return 0.0


def _generic_penalty(normalized_name: str) -> float:
    tokens = set(normalized_name.split())
    overlap = tokens & GENERIC_NAME_TOKENS
    return min(len(overlap) * 8.0, 24.0)


def _agency_ambiguity_penalty(candidate_type: str) -> float:
    if candidate_type in {"collection_agency", "servicer", "unknown"}:
        return 10.0
    return 0.0


def score_entity(
    *,
    complaint_count: int,
    state_count: int,
    products: list[str],
    narrative_count: int,
    last_seen_at: str | None,
    normalized_name: str,
) -> float:
    """Score a company entity 0–100."""
    if complaint_count <= 0:
        return 0.0
    score = 0.0
    score += min(complaint_count * 2, 30)
    score += min(state_count * 5, 50)
    if products:
        weights = [product_relevance_weight(p) for p in products]
        score += (sum(weights) / len(weights)) * 15
    if narrative_count > 0:
        score += min(narrative_count * 0.5, 10)
    score += _recency_bonus(last_seen_at)
    score -= _generic_penalty(normalized_name)
    return max(0.0, min(100.0, round(score, 2)))


def score_candidate(
    *,
    entity_score: float,
    candidate_type: str,
    from_narrative: bool,
    has_domain: bool,
    complaint_count: int,
) -> float:
    """Score an individual brand candidate 0–100."""
    score = entity_score * 0.6
    if candidate_type in {"company_name", "legal_entity", "dba"}:
        score += 20
    elif candidate_type == "domain":
        score += 15
    elif candidate_type == "possible_brand":
        score += 8
    if has_domain:
        score += 5
    if complaint_count >= 10:
        score += 5
    if from_narrative:
        score -= 12
    score -= _agency_ambiguity_penalty(candidate_type)
    return max(0.0, min(100.0, round(score, 2)))


def score_band(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "good"
    if score >= 50:
        return "review"
    if score >= 30:
        return "weak"
    return "reject"
