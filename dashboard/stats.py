"""Station yield statistics and slot recommendation helpers."""

from __future__ import annotations


def compute_yield_pct(*, keyword_hits: int, chunks: int) -> float:
    """Keyword hits per processed chunk, as a percentage."""
    if chunks <= 0:
        return 0.0
    return round((keyword_hits / chunks) * 100.0, 2)


def derive_slot_recommendation(
    *,
    enabled: bool,
    status: str,
    chunks_7d: int,
    keyword_hits_7d: int,
    yield_pct: float,
    min_chunks_for_swap: int = 50,
) -> str:
    """Operator hint for limited ingest slots: keep | swap | fix | review | bench."""
    if not enabled:
        return "bench"
    if status in {"down", "stale"}:
        return "fix"
    if chunks_7d >= min_chunks_for_swap and keyword_hits_7d == 0:
        return "swap"
    if chunks_7d >= min_chunks_for_swap and yield_pct < 0.3 and keyword_hits_7d < 2:
        return "review"
    return "keep"


def derive_review_tier(*, has_keywords: bool, has_ad_detection: bool) -> str:
    """Classify a chunk for the review inbox: A (both), B (LLM ad), C (keyword only)."""
    if has_ad_detection and has_keywords:
        return "A"
    if has_ad_detection:
        return "B"
    if has_keywords:
        return "C"
    return "—"
