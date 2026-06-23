"""Rollout observability counters for consumer_personal_loan keyword gating."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from shared.consumer_personal_loan import (
    CLASSIFIER_NAME,
    CLASSIFIER_VERSION,
    ConsumerPersonalLoanClassification,
    KeywordHitGateResult,
    TAXONOMY_VERSION,
    classification_log_extra,
)

logger = logging.getLogger("worker")

SUMMARY_EVERY_CHUNKS = 50


@dataclass
class ClassifierRolloutStats:
    chunks_processed: int = 0
    target_phrase_matches: int = 0
    accepted_keyword_hits: int = 0
    rejected_after_classifier: int = 0
    review_after_classifier_not_persisted: int = 0
    rejection_reasons: Counter[str] = field(default_factory=Counter)

    def record_chunk_processed(self) -> None:
        self.chunks_processed += 1

    def record_gate(
        self,
        *,
        chunk_id: int,
        raw_match_count: int,
        gate: KeywordHitGateResult,
    ) -> None:
        if raw_match_count <= 0:
            return

        self.target_phrase_matches += 1
        classification = gate.classification
        if classification is None:
            return

        log_extra: dict[str, object] = {
            "chunk_id": chunk_id,
            "raw_match_count": raw_match_count,
            "persisted_match_count": len(gate.matches),
            **classification_log_extra(classification),
        }

        if gate.persisted:
            self.accepted_keyword_hits += len(gate.matches)
            logger.info("keyword classifier accepted hits", extra=log_extra)
            return

        if classification.status == "review":
            self.review_after_classifier_not_persisted += 1
            logger.info("keyword classifier review not persisted", extra=log_extra)
            return

        self.rejected_after_classifier += 1
        self.rejection_reasons[classification.reason] += 1
        logger.info("keyword classifier rejected hits", extra=log_extra)

    def maybe_log_summary(self) -> None:
        if self.chunks_processed == 0:
            return
        if self.chunks_processed % SUMMARY_EVERY_CHUNKS != 0:
            return
        top_reasons = dict(self.rejection_reasons.most_common(5))
        logger.info(
            "keyword classifier rollout summary",
            extra={
                "classifier_name": CLASSIFIER_NAME,
                "classifier_version": CLASSIFIER_VERSION,
                "taxonomy_version": TAXONOMY_VERSION,
                "chunks_processed": self.chunks_processed,
                "target_phrase_matches": self.target_phrase_matches,
                "accepted_keyword_hits": self.accepted_keyword_hits,
                "rejected_after_classifier": self.rejected_after_classifier,
                "review_after_classifier_not_persisted": (
                    self.review_after_classifier_not_persisted
                ),
                "top_rejection_reasons": top_reasons,
            },
        )
