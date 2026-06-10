"""Tests for dashboard yield and slot recommendation helpers."""

from __future__ import annotations

from dashboard.stats import compute_yield_pct, derive_review_tier, derive_slot_recommendation


def test_compute_yield_pct() -> None:
    assert compute_yield_pct(keyword_hits=5, chunks=200) == 2.5
    assert compute_yield_pct(keyword_hits=0, chunks=0) == 0.0


def test_derive_slot_recommendation_swap_dead_slot() -> None:
    assert (
        derive_slot_recommendation(
            enabled=True,
            status="live",
            chunks_7d=100,
            keyword_hits_7d=0,
            yield_pct=0.0,
        )
        == "swap"
    )


def test_derive_slot_recommendation_fix_when_down() -> None:
    assert (
        derive_slot_recommendation(
            enabled=True,
            status="down",
            chunks_7d=100,
            keyword_hits_7d=10,
            yield_pct=10.0,
        )
        == "fix"
    )


def test_derive_slot_recommendation_keep_productive_station() -> None:
    assert (
        derive_slot_recommendation(
            enabled=True,
            status="live",
            chunks_7d=100,
            keyword_hits_7d=8,
            yield_pct=8.0,
        )
        == "keep"
    )


def test_derive_review_tier() -> None:
    assert derive_review_tier(has_keywords=True, has_ad_detection=True) == "A"
    assert derive_review_tier(has_keywords=False, has_ad_detection=True) == "B"
    assert derive_review_tier(has_keywords=True, has_ad_detection=False) == "C"
    assert derive_review_tier(has_keywords=False, has_ad_detection=False) == "—"
