"""Consumer personal loan vertical taxonomy and transcript classifier.

Pipeline gating (worker/consumer.py):
1. ``find_keyword_matches`` scans only ``target_vertical_keywords`` phrases.
2. Classifier runs only when at least one target phrase matched in the transcript.
3. ``should_record_keyword_hits`` persists rows only for ``accept`` status.

Ambiguous-only transcripts (soft_exclude / weak_single_terms with no target phrase)
never reach the classifier and never write ``keyword_hits``. There is no separate
keyword review queue; ``review`` classifier outcomes are logged but not persisted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from shared.models import LoanKeywordEntry

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_TAXONOMY_PATH = CONFIG_DIR / "consumer_personal_loan_taxonomy.yaml"

VERTICAL_ID = "consumer_personal_loan"

CLASSIFIER_NAME = "consumer_personal_loan"
CLASSIFIER_VERSION = "consumer_personal_loan_v1"
TAXONOMY_VERSION = "2026-06-19"

ClassificationStatus = Literal["accept", "review", "reject"]

CASH_ADVANCE_PHRASES = frozenset({"cash advance", "cash advances"})

_LOAN_ANCHOR_TOKENS = (
    "personal",
    "installment",
    "payday",
    "emergency",
    "consumer",
    "bad credit",
    "no credit check",
    "loan matching",
    "loan request",
    "loan application",
    "apply for a loan",
    "cash loan",
    "same day",
    "same-day",
    "next day",
    "direct lender",
    "personal funding",
    "consumer lending",
    "funding request",
    "funds as soon as",
    "checking account required",
    "online loan",
    "fast loan",
    "quick loan",
    "short term",
    "short-term",
    "unsecured",
    "money deposited",
)


@dataclass(frozen=True)
class ConsumerPersonalLoanTaxonomy:
    target_phrases: tuple[str, ...]
    intent_phrases: tuple[str, ...]
    excluded_phrases: tuple[str, ...]
    soft_exclude_phrases: tuple[str, ...]
    weak_single_terms: tuple[str, ...]


@dataclass(frozen=True)
class ConsumerPersonalLoanClassification:
    status: ClassificationStatus
    reason: str
    score: int
    vertical: str = VERTICAL_ID
    target_hits: tuple[str, ...] = ()
    intent_hits: tuple[str, ...] = ()
    matched_exclusions: tuple[str, ...] = ()
    soft_exclude_hits: tuple[str, ...] = ()
    weak_single_term_hits: tuple[str, ...] = ()
    classifier_name: str = CLASSIFIER_NAME
    classifier_version: str = CLASSIFIER_VERSION
    taxonomy_version: str = TAXONOMY_VERSION


@dataclass(frozen=True)
class KeywordHitGateResult:
    """Result of classifier gating before keyword_hits persistence."""

    matches: tuple
    classification: ConsumerPersonalLoanClassification | None
    persisted: bool


def _flatten_grouped_phrases(data: object) -> list[str]:
    if not isinstance(data, dict):
        return []
    phrases: list[str] = []
    for group in data.values():
        if isinstance(group, list):
            for item in group:
                if isinstance(item, str) and item.strip():
                    phrases.append(item.strip())
    return phrases


def _flatten_list_phrases(data: object) -> list[str]:
    if not isinstance(data, list):
        return []
    return [item.strip() for item in data if isinstance(item, str) and item.strip()]


def _dedupe_preserve_order(phrases: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for phrase in phrases:
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(phrase)
    return tuple(ordered)


@lru_cache(maxsize=4)
def load_consumer_personal_loan_taxonomy(
    path: str | None = None,
) -> ConsumerPersonalLoanTaxonomy:
    config_path = Path(path) if path else DEFAULT_TAXONOMY_PATH
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    target = _flatten_grouped_phrases(data.get("target_vertical_keywords"))
    intent = _flatten_grouped_phrases(data.get("intent_qualifiers"))
    excluded = _flatten_grouped_phrases(data.get("excluded_vertical_keywords"))
    soft = _flatten_grouped_phrases(data.get("soft_exclude_keywords"))
    weak = _flatten_list_phrases(data.get("weak_single_terms"))

    return ConsumerPersonalLoanTaxonomy(
        target_phrases=_dedupe_preserve_order(target),
        intent_phrases=_dedupe_preserve_order(intent),
        excluded_phrases=_dedupe_preserve_order(excluded),
        soft_exclude_phrases=_dedupe_preserve_order(soft),
        weak_single_terms=_dedupe_preserve_order(weak),
    )


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", re.IGNORECASE)


def _match_phrases(text: str, phrases: tuple[str, ...]) -> tuple[str, ...]:
    if not text or not phrases:
        return ()
    matched: list[str] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        if _phrase_pattern(phrase).search(text):
            matched.append(phrase)
    return tuple(matched)


def _match_weak_single_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    if not text or not terms:
        return ()
    matched: list[str] = []
    for term in terms:
        if _phrase_pattern(term).search(text):
            matched.append(term)
    return tuple(matched)


def _has_consumer_loan_anchor(target_hits: tuple[str, ...]) -> bool:
    for phrase in target_hits:
        lower = phrase.lower()
        if lower in CASH_ADVANCE_PHRASES:
            continue
        if any(token in lower for token in _LOAN_ANCHOR_TOKENS):
            return True
        if " loan" in lower or lower.endswith(" loan") or lower.startswith("loan "):
            return True
    return False


def _cash_advance_only_without_intent(
    target_hits: tuple[str, ...],
    intent_hits: tuple[str, ...],
) -> bool:
    has_cash_advance = any(hit.lower() in CASH_ADVANCE_PHRASES for hit in target_hits)
    if not has_cash_advance:
        return False
    if _has_consumer_loan_anchor(target_hits):
        return False
    return len(intent_hits) < 1


def _target_confidence(phrase: str) -> float:
    lowered = phrase.lower()
    if any(
        token in lowered
        for token in (
            "payday",
            "installment",
            "personal loan",
            "bad credit",
            "no credit check",
            "emergency loan",
        )
    ):
        return 0.90
    if lowered in CASH_ADVANCE_PHRASES:
        return 0.85
    if any(token in lowered for token in ("apply", "matching", "lender", "deposit")):
        return 0.85
    return 0.80


def target_phrases_as_keyword_entries(
    taxonomy: ConsumerPersonalLoanTaxonomy | None = None,
) -> list[LoanKeywordEntry]:
    tax = taxonomy or load_consumer_personal_loan_taxonomy()
    return [
        LoanKeywordEntry(phrase=phrase, confidence=_target_confidence(phrase))
        for phrase in tax.target_phrases
    ]


def classify_consumer_personal_loan_text(
    text: str,
    *,
    taxonomy: ConsumerPersonalLoanTaxonomy | None = None,
) -> ConsumerPersonalLoanClassification:
    """Classify transcript text for consumer_personal_loan vertical."""
    tax = taxonomy or load_consumer_personal_loan_taxonomy()

    target_hits = _match_phrases(text, tax.target_phrases)
    intent_hits = _match_phrases(text, tax.intent_phrases)
    matched_exclusions = _match_phrases(text, tax.excluded_phrases)
    soft_exclude_hits = _match_phrases(text, tax.soft_exclude_phrases)
    weak_single_term_hits = _match_weak_single_terms(text, tax.weak_single_terms)

    target_count = len(target_hits)
    intent_count = len(intent_hits)
    excluded_count = len(matched_exclusions)
    soft_count = len(soft_exclude_hits)
    weak_count = len(weak_single_term_hits)

    score = (
        target_count * 20
        + intent_count * 8
        - soft_count * 10
        - weak_count * 5
    )

    if excluded_count:
        return ConsumerPersonalLoanClassification(
            status="reject",
            reason="excluded_vertical",
            score=score,
            target_hits=target_hits,
            intent_hits=intent_hits,
            matched_exclusions=matched_exclusions,
            soft_exclude_hits=soft_exclude_hits,
            weak_single_term_hits=weak_single_term_hits,
        )

    if _cash_advance_only_without_intent(target_hits, intent_hits):
        return ConsumerPersonalLoanClassification(
            status="reject",
            reason="cash_advance_requires_intent",
            score=score,
            target_hits=target_hits,
            intent_hits=intent_hits,
            matched_exclusions=matched_exclusions,
            soft_exclude_hits=soft_exclude_hits,
            weak_single_term_hits=weak_single_term_hits,
        )

    if target_count >= 1 and intent_count >= 1:
        return ConsumerPersonalLoanClassification(
            status="accept",
            reason="target_vertical_with_intent",
            score=score,
            target_hits=target_hits,
            intent_hits=intent_hits,
            matched_exclusions=matched_exclusions,
            soft_exclude_hits=soft_exclude_hits,
            weak_single_term_hits=weak_single_term_hits,
        )

    if target_count >= 1:
        return ConsumerPersonalLoanClassification(
            status="review",
            reason="target_vertical_no_intent",
            score=score,
            target_hits=target_hits,
            intent_hits=intent_hits,
            matched_exclusions=matched_exclusions,
            soft_exclude_hits=soft_exclude_hits,
            weak_single_term_hits=weak_single_term_hits,
        )

    if soft_count > 0:
        return ConsumerPersonalLoanClassification(
            status="reject",
            reason="ambiguous_vertical",
            score=score,
            target_hits=target_hits,
            intent_hits=intent_hits,
            matched_exclusions=matched_exclusions,
            soft_exclude_hits=soft_exclude_hits,
            weak_single_term_hits=weak_single_term_hits,
        )

    if weak_count > 0:
        return ConsumerPersonalLoanClassification(
            status="reject",
            reason="weak_single_term_only",
            score=score,
            target_hits=target_hits,
            intent_hits=intent_hits,
            matched_exclusions=matched_exclusions,
            soft_exclude_hits=soft_exclude_hits,
            weak_single_term_hits=weak_single_term_hits,
        )

    return ConsumerPersonalLoanClassification(
        status="reject",
        reason="no_target_vertical",
        score=score,
        target_hits=target_hits,
        intent_hits=intent_hits,
        matched_exclusions=matched_exclusions,
        soft_exclude_hits=soft_exclude_hits,
        weak_single_term_hits=weak_single_term_hits,
    )


def should_record_keyword_hits(classification: ConsumerPersonalLoanClassification) -> bool:
    """Persist keyword_hits only for high-confidence accept decisions."""
    return classification.status == "accept"


def classification_log_extra(
    classification: ConsumerPersonalLoanClassification,
) -> dict[str, object]:
    """Structured log fields for classifier observability."""
    return {
        "classifier_name": classification.classifier_name,
        "classifier_version": classification.classifier_version,
        "taxonomy_version": classification.taxonomy_version,
        "classifier_status": classification.status,
        "classifier_reason": classification.reason,
        "classifier_score": classification.score,
        "target_hits": list(classification.target_hits),
        "intent_hits": list(classification.intent_hits),
    }


def gate_keyword_matches_for_persistence(
    transcript: str,
    matches: list,
) -> KeywordHitGateResult:
    """Classify transcript and return matches allowed for keyword_hits insert."""
    if not matches:
        return KeywordHitGateResult((), None, False)
    classification = classify_consumer_personal_loan_text(transcript)
    if should_record_keyword_hits(classification):
        return KeywordHitGateResult(tuple(matches), classification, True)
    return KeywordHitGateResult((), classification, False)


def filter_keyword_matches_for_persistence(
    transcript: str,
    matches: list,
) -> list:
    """Apply classifier gate before writing keyword_hits (mirrors worker/consumer.py)."""
    return list(gate_keyword_matches_for_persistence(transcript, matches).matches)
