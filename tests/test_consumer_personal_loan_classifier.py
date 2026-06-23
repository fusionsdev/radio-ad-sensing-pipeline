"""Tests for consumer_personal_loan vertical taxonomy classifier."""

from __future__ import annotations

import pytest

from shared.consumer_personal_loan import (
    VERTICAL_ID,
    classify_consumer_personal_loan_text,
    load_consumer_personal_loan_taxonomy,
    should_record_keyword_hits,
    target_phrases_as_keyword_entries,
)


@pytest.fixture
def taxonomy():
    return load_consumer_personal_loan_taxonomy()


@pytest.mark.parametrize(
    ("text", "expected_exclusion"),
    [
        ("Call now for tax relief on your back taxes", "tax relief"),
        ("We help with back taxes and IRS issues", "back taxes"),
        ("IRS tax debt resolution specialists", "IRS"),
        ("Get term life insurance with low premiums", "term life insurance"),
        ("Apply for a business loan today", "business loan"),
        ("Same-day business funding up to $500k", "business funding"),
        ("Merchant cash advance for your storefront", "merchant cash advance"),
        ("Lower your mortgage refinance rate now", "refinance"),
        ("Get an auto loan with zero down", "auto loan"),
        ("Student loan forgiveness program enrollment", "student loan forgiveness"),
        ("Debt relief and debt settlement plans", "debt relief"),
        ("Professional credit repair services available", "credit repair"),
    ],
)
def test_rejects_unrelated_vertical_false_positives(
    taxonomy,
    text: str,
    expected_exclusion: str,
) -> None:
    result = classify_consumer_personal_loan_text(text, taxonomy=taxonomy)
    assert result.status == "reject"
    assert result.reason == "excluded_vertical"
    assert expected_exclusion in result.matched_exclusions


@pytest.mark.parametrize(
    "text",
    [
        "Submit your personal loan application online in minutes",
        "Installment loans online with fast approval today",
        "Need an emergency cash loan? Apply now",
        "Bad credit personal loan with monthly payments and APR disclosure",
        "Apply for a loan online through our lender network",
        "Our loan matching service connects you with direct lenders",
        "Funds as soon as next business day with direct deposit",
        "Checking account required for same-day personal loan approval",
    ],
)
def test_accepts_consumer_personal_loan_with_intent(taxonomy, text: str) -> None:
    result = classify_consumer_personal_loan_text(text, taxonomy=taxonomy)
    assert result.status == "accept"
    assert result.reason == "target_vertical_with_intent"
    assert result.target_hits
    assert result.intent_hits
    assert should_record_keyword_hits(result)


@pytest.mark.parametrize(
    "text",
    [
        "We offer financing options for qualified buyers",
        "Funding available for qualified applicants",
        "Credit assistance programs may help",
        "Ask about our payment plan",
        "Hardship assistance for eligible customers",
    ],
)
def test_ambiguous_soft_exclude_rejects_without_target(taxonomy, text: str) -> None:
    result = classify_consumer_personal_loan_text(text, taxonomy=taxonomy)
    assert result.status == "reject"
    assert result.reason == "ambiguous_vertical"
    assert not result.target_hits
    assert not should_record_keyword_hits(result)


def test_target_without_intent_does_not_persist(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "This segment mentioned payday loans during the news hour.",
        taxonomy=taxonomy,
    )
    assert result.status == "review"
    assert result.reason == "target_vertical_no_intent"
    assert "payday loans" in result.target_hits
    assert not should_record_keyword_hits(result)


def test_apply_online_is_intent_not_target(taxonomy) -> None:
    assert "apply online" not in taxonomy.target_phrases
    assert "apply online" in taxonomy.intent_phrases


def test_cash_advance_credit_card_excluded(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "Your credit card cash advance fee may apply this cycle.",
        taxonomy=taxonomy,
    )
    assert result.status == "reject"
    assert result.reason == "excluded_vertical"
    assert "credit card cash advance" in result.matched_exclusions


def test_cash_advance_alone_rejects_without_intent(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "They mentioned cash advance on the program.",
        taxonomy=taxonomy,
    )
    assert result.status == "reject"
    assert result.reason == "cash_advance_requires_intent"
    assert not should_record_keyword_hits(result)


def test_cash_advance_with_intent_accepts(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "Request a cash advance today with fast approval from online lenders.",
        taxonomy=taxonomy,
    )
    assert result.status == "accept"
    assert should_record_keyword_hits(result)


def test_weak_single_term_only_rejects(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "They mentioned loan and cash on the show.",
        taxonomy=taxonomy,
    )
    assert result.status == "reject"
    assert result.reason == "weak_single_term_only"
    assert not should_record_keyword_hits(result)


def test_no_target_vertical_rejects(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "Weather forecast looks sunny this weekend.",
        taxonomy=taxonomy,
    )
    assert result.status == "reject"
    assert result.reason == "no_target_vertical"


def test_exclusion_wins_over_target_phrase(taxonomy) -> None:
    result = classify_consumer_personal_loan_text(
        "Debt relief and personal loan options for back taxes",
        taxonomy=taxonomy,
    )
    assert result.status == "reject"
    assert result.reason == "excluded_vertical"


def test_taxonomy_loads_target_and_exclusion_layers(taxonomy) -> None:
    assert "personal loan" in taxonomy.target_phrases
    assert "apply online" not in taxonomy.target_phrases
    assert "apply online" in taxonomy.intent_phrases
    assert "apply" in taxonomy.intent_phrases
    assert "credit card cash advance" in taxonomy.excluded_phrases


def test_target_phrases_as_keyword_entries(taxonomy) -> None:
    entries = target_phrases_as_keyword_entries(taxonomy)
    phrases = {entry.phrase for entry in entries}
    assert "payday loan" in phrases
    assert "cash advance" in phrases
    assert all(entry.confidence >= 0.6 for entry in entries)


def test_scoring_increases_with_target_and_intent(taxonomy) -> None:
    weak = classify_consumer_personal_loan_text("loan cash money", taxonomy=taxonomy)
    strong = classify_consumer_personal_loan_text(
        "Apply online for a personal loan with fast approval today",
        taxonomy=taxonomy,
    )
    assert strong.score > weak.score


def test_vertical_id_constant() -> None:
    result = classify_consumer_personal_loan_text(
        "Apply for a personal loan online today",
    )
    assert result.vertical == VERTICAL_ID
    assert result.classifier_name == "consumer_personal_loan"
    assert result.classifier_version == "consumer_personal_loan_v1"
    assert result.taxonomy_version == "2026-06-19"
