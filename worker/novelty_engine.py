"""Novelty-first keyword discovery engine — independent of radio worker."""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.db import get_connection, retry_on_busy, transaction
from worker.opportunity_scoring import (
    OpportunityScoreInput,
    calculate_opportunity_score,
    suggest_action,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

try:  # pragma: no cover - fallback only when dev dependency is absent
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    class _FuzzFallback:
        @staticmethod
        def ratio(left: str, right: str) -> float:
            return SequenceMatcher(None, left, right).ratio() * 100.0

    fuzz = _FuzzFallback()  # type: ignore[assignment]

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


@dataclass(frozen=True)
class NoveltyRules:
    report_novelty_score: float
    report_opportunity_score: float
    min_source_confidence: float
    dashboard_only_score: float
    noise_score: float
    near_duplicate_ratio: float
    report_known_brands: bool
    report_known_keywords: bool
    report_excluded_verticals: bool
    require_evidence_text: bool
    require_source_url: bool


@dataclass(frozen=True)
class NoveltyConfig:
    known_brands: frozenset[str]
    known_keywords: frozenset[str]
    excluded_verticals: frozenset[str]
    rules: NoveltyRules


@dataclass(frozen=True)
class CandidateInput:
    candidate_text: str
    vertical: str | None = None
    sub_vertical: str | None = None
    candidate_type: str = "keyword"
    source_type: str = "manual"
    source_url: str | None = None
    evidence_text: str | None = None
    source_confidence: float = 0.0
    extraction_confidence: float = 0.0
    raw_item_id: int | None = None


@dataclass(frozen=True)
class NoveltyEvaluation:
    normalized_text: str
    novelty_status: str
    novelty_score: float
    opportunity_score: float
    known_match: str | None
    known_match_type: str | None
    similarity_score: float | None
    reason: str
    report_eligible: bool
    report_suppressed_reason: str | None


def normalize_candidate_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    lowered = text.strip().lower()
    cleaned = _PUNCT_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def _flatten_brands(data: dict[str, Any]) -> frozenset[str]:
    brands: set[str] = set()
    known = data.get("known_brands", {})
    if isinstance(known, dict):
        for entries in known.values():
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, str) and item.strip():
                        brands.add(normalize_candidate_text(item))
    return frozenset(brands)


def _flatten_keywords(data: dict[str, Any]) -> frozenset[str]:
    keywords: set[str] = set()
    entries = data.get("known_generic_keywords", [])
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, str) and item.strip():
                keywords.add(normalize_candidate_text(item))
    return frozenset(keywords)


def _flatten_excluded(data: dict[str, Any]) -> frozenset[str]:
    entries = data.get("excluded_verticals", [])
    normalized: set[str] = set()
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, str) and item.strip():
                normalized.add(item.strip().lower())
    return frozenset(normalized)


def load_novelty_config(
    *,
    known_entities_path: Path | None = None,
    known_keywords_path: Path | None = None,
    excluded_verticals_path: Path | None = None,
    novelty_rules_path: Path | None = None,
) -> NoveltyConfig:
    entities_path = known_entities_path or CONFIG_DIR / "known_entities.yaml"
    keywords_path = known_keywords_path or CONFIG_DIR / "known_keywords.yaml"
    excluded_path = excluded_verticals_path or CONFIG_DIR / "excluded_verticals.yaml"
    rules_path = novelty_rules_path or CONFIG_DIR / "novelty_rules.yaml"

    with entities_path.open(encoding="utf-8") as handle:
        entities = yaml.safe_load(handle) or {}
    with keywords_path.open(encoding="utf-8") as handle:
        keywords = yaml.safe_load(handle) or {}
    with excluded_path.open(encoding="utf-8") as handle:
        excluded = yaml.safe_load(handle) or {}
    with rules_path.open(encoding="utf-8") as handle:
        rules_data = yaml.safe_load(handle) or {}

    thresholds = rules_data.get("thresholds", {})
    reporting = rules_data.get("reporting", {})
    rules = NoveltyRules(
        report_novelty_score=float(thresholds.get("report_novelty_score", 75)),
        report_opportunity_score=float(thresholds.get("report_opportunity_score", 70)),
        min_source_confidence=float(thresholds.get("min_source_confidence", 0.70)),
        dashboard_only_score=float(thresholds.get("dashboard_only_score", 40)),
        noise_score=float(thresholds.get("noise_score", 20)),
        near_duplicate_ratio=float(thresholds.get("near_duplicate_ratio", 85)),
        report_known_brands=bool(reporting.get("report_known_brands", False)),
        report_known_keywords=bool(reporting.get("report_known_keywords", False)),
        report_excluded_verticals=bool(reporting.get("report_excluded_verticals", False)),
        require_evidence_text=bool(reporting.get("require_evidence_text", True)),
        require_source_url=bool(reporting.get("require_source_url", True)),
    )

    return NoveltyConfig(
        known_brands=_flatten_brands(entities),
        known_keywords=_flatten_keywords(keywords),
        excluded_verticals=_flatten_excluded(excluded),
        rules=rules,
    )


def _best_fuzzy_match(
    normalized: str,
    candidates: frozenset[str],
) -> tuple[str | None, float]:
    best_match: str | None = None
    best_score = 0.0
    for candidate in candidates:
        score = float(fuzz.ratio(normalized, candidate))
        if score > best_score:
            best_score = score
            best_match = candidate
    return best_match, best_score


def _calculate_novelty_score(
    *,
    normalized: str,
    status: str,
    source_confidence: float,
    word_count: int,
    rules: NoveltyRules,
) -> float:
    if status == "known_duplicate":
        return 5.0
    if status == "near_duplicate":
        return rules.dashboard_only_score
    if status == "generic":
        return rules.dashboard_only_score
    if status == "excluded_vertical":
        return 0.0
    if status == "weak_evidence":
        return rules.dashboard_only_score - 5.0
    if status == "noise":
        return rules.noise_score

    score = 55.0 + min(25.0, word_count * 5.0)
    score += source_confidence * 15.0
    if word_count <= 2:
        score -= 10.0
    return round(max(0.0, min(100.0, score)), 2)


def evaluate_candidate(
    candidate: CandidateInput,
    config: NoveltyConfig | None = None,
) -> NoveltyEvaluation:
    """Classify a candidate and compute novelty / report eligibility."""
    cfg = config or load_novelty_config()
    rules = cfg.rules
    normalized = normalize_candidate_text(candidate.candidate_text)
    word_count = len(normalized.split()) if normalized else 0
    vertical_key = (candidate.vertical or "").strip().lower()

    known_match: str | None = None
    known_match_type: str | None = None
    similarity_score: float | None = None
    status = "new"
    reason = "Novel candidate phrase"

    if not normalized or word_count == 0:
        status = "noise"
        reason = "Empty or unparseable candidate text"
    elif vertical_key and vertical_key in cfg.excluded_verticals:
        status = "excluded_vertical"
        reason = f"Vertical '{vertical_key}' is excluded"
    elif normalized in cfg.excluded_verticals:
        status = "excluded_vertical"
        reason = f"Candidate maps to excluded vertical '{normalized}'"
    elif normalized in cfg.known_brands:
        status = "known_duplicate"
        known_match = normalized
        known_match_type = "brand"
        reason = f"Exact match to known brand '{normalized}'"
    elif normalized in cfg.known_keywords:
        status = "generic"
        known_match = normalized
        known_match_type = "generic_keyword"
        reason = f"Exact match to known generic keyword '{normalized}'"
    else:
        brand_match, brand_score = _best_fuzzy_match(normalized, cfg.known_brands)
        if brand_match and brand_score >= rules.near_duplicate_ratio:
            status = "near_duplicate"
            known_match = brand_match
            known_match_type = "brand"
            similarity_score = brand_score
            reason = f"Near duplicate of known brand '{brand_match}' ({brand_score:.0f}%)"
        else:
            keyword_match, keyword_score = _best_fuzzy_match(normalized, cfg.known_keywords)
            if keyword_match and keyword_score >= rules.near_duplicate_ratio:
                status = "near_duplicate"
                known_match = keyword_match
                known_match_type = "generic_keyword"
                similarity_score = keyword_score
                reason = (
                    f"Near duplicate of known generic keyword '{keyword_match}' "
                    f"({keyword_score:.0f}%)"
                )
            elif any(
                normalized == kw or normalized.startswith(kw + " ") or normalized.endswith(" " + kw)
                for kw in cfg.known_keywords
                if len(kw.split()) == 1
            ):
                status = "generic"
                reason = "Contains known generic keyword fragment"

    if status == "new":
        if rules.require_evidence_text and not (candidate.evidence_text or "").strip():
            status = "weak_evidence"
            reason = "Missing evidence text"
        elif rules.require_source_url and not (candidate.source_url or "").strip():
            status = "weak_evidence"
            reason = "Missing source URL"

    novelty_score = _calculate_novelty_score(
        normalized=normalized,
        status=status,
        source_confidence=candidate.source_confidence,
        word_count=word_count,
        rules=rules,
    )

    opportunity_score = calculate_opportunity_score(
        OpportunityScoreInput(
            normalized_text=normalized,
            vertical=candidate.vertical,
            novelty_status=status,
            source_confidence=candidate.source_confidence,
            extraction_confidence=candidate.extraction_confidence,
            word_count=word_count,
        )
    )

    if status == "new" and novelty_score < rules.report_novelty_score:
        status = "needs_review"
        reason = f"Novel but below novelty threshold ({novelty_score:.0f} < {rules.report_novelty_score:.0f})"

    report_eligible = (
        status in {"new", "needs_review"}
        and novelty_score >= rules.report_novelty_score
        and opportunity_score >= rules.report_opportunity_score
        and candidate.source_confidence >= rules.min_source_confidence
        and not (vertical_key and vertical_key in cfg.excluded_verticals)
        and status != "known_duplicate"
        and (not rules.require_evidence_text or bool((candidate.evidence_text or "").strip()))
        and (not rules.require_source_url or bool((candidate.source_url or "").strip()))
    )

    suppressed: str | None = None
    if not report_eligible:
        if status == "known_duplicate":
            suppressed = "known_brand"
        elif status == "near_duplicate":
            suppressed = "near_duplicate"
        elif status == "generic":
            suppressed = "generic_keyword"
        elif status == "excluded_vertical":
            suppressed = "excluded_vertical"
        elif status == "weak_evidence":
            suppressed = "weak_evidence"
        elif status == "noise":
            suppressed = "noise"
        elif novelty_score < rules.report_novelty_score:
            suppressed = "low_novelty_score"
        elif opportunity_score < rules.report_opportunity_score:
            suppressed = "low_opportunity_score"
        elif candidate.source_confidence < rules.min_source_confidence:
            suppressed = "low_source_confidence"
        else:
            suppressed = "policy"

    return NoveltyEvaluation(
        normalized_text=normalized,
        novelty_status=status,
        novelty_score=novelty_score,
        opportunity_score=opportunity_score,
        known_match=known_match,
        known_match_type=known_match_type,
        similarity_score=similarity_score,
        reason=reason,
        report_eligible=report_eligible,
        report_suppressed_reason=suppressed,
    )


@retry_on_busy()
def insert_candidate(
    db_path: str | Path,
    candidate: CandidateInput,
) -> int:
    """Insert candidate_terms row and return its id."""
    normalized = normalize_candidate_text(candidate.candidate_text)
    now = time.time()
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO candidate_terms (
                    raw_item_id, candidate_text, normalized_text, candidate_type,
                    vertical, sub_vertical, evidence_text, source_type, source_url,
                    source_confidence, extraction_confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.raw_item_id,
                    candidate.candidate_text,
                    normalized,
                    candidate.candidate_type,
                    candidate.vertical,
                    candidate.sub_vertical,
                    candidate.evidence_text,
                    candidate.source_type,
                    candidate.source_url,
                    candidate.source_confidence,
                    candidate.extraction_confidence,
                    now,
                ),
            )
            return int(cursor.lastrowid)
    finally:
        conn.close()


@retry_on_busy()
def process_candidate(
    db_path: str | Path,
    candidate: CandidateInput,
    *,
    config: NoveltyConfig | None = None,
    candidate_id: int | None = None,
) -> tuple[int, NoveltyEvaluation]:
    """Evaluate candidate, persist novelty_results, optionally keyword_opportunities."""
    cfg = config or load_novelty_config()
    evaluation = evaluate_candidate(candidate, cfg)
    cid = candidate_id if candidate_id is not None else insert_candidate(db_path, candidate)
    now = time.time()

    conn = get_connection(db_path)
    try:
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO novelty_results (
                    candidate_id, normalized_text, novelty_status, novelty_score,
                    opportunity_score, known_match, known_match_type, similarity_score,
                    reason, report_eligible, report_suppressed_reason, reviewed_status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    evaluation.normalized_text,
                    evaluation.novelty_status,
                    evaluation.novelty_score,
                    evaluation.opportunity_score,
                    evaluation.known_match,
                    evaluation.known_match_type,
                    evaluation.similarity_score,
                    evaluation.reason,
                    1 if evaluation.report_eligible else 0,
                    evaluation.report_suppressed_reason,
                    "pending",
                    now,
                ),
            )
            novelty_id = int(cursor.lastrowid)

            if evaluation.report_eligible:
                conn.execute(
                    """
                    INSERT INTO keyword_opportunities (
                        candidate_id, opportunity_text, opportunity_type, vertical,
                        sub_vertical, source_type, source_url, evidence_text,
                        novelty_score, opportunity_score, risk_level, suggested_action,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        candidate.candidate_text,
                        candidate.candidate_type,
                        candidate.vertical,
                        candidate.sub_vertical,
                        candidate.source_type,
                        candidate.source_url,
                        candidate.evidence_text,
                        evaluation.novelty_score,
                        evaluation.opportunity_score,
                        "medium",
                        suggest_action(evaluation.opportunity_score, candidate.vertical),
                        "new",
                        now,
                    ),
                )
            _ = novelty_id
    finally:
        conn.close()

    return cid, evaluation
