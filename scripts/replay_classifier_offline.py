"""Replay consumer_personal_loan gate against historical transcripts."""

from __future__ import annotations

import sqlite3
from collections import Counter

from shared.config import load_loan_keywords
from shared.consumer_personal_loan import (
    CLASSIFIER_NAME,
    CLASSIFIER_VERSION,
    TAXONOMY_VERSION,
    classification_log_extra,
    gate_keyword_matches_for_persistence,
)
from worker.keywords import find_keyword_matches


def main(db_path: str = "/app/data/pipeline.db") -> None:
    keywords = load_loan_keywords()
    phrases = [k.phrase.lower() for k in keywords]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    candidates = []
    for row in conn.execute(
        """
        SELECT ch.id, s.name AS station, t.text
        FROM transcripts t
        JOIN chunks ch ON ch.id = t.chunk_id
        JOIN stations s ON s.id = ch.station_id
        """
    ):
        if any(p in row["text"].lower() for p in phrases):
            candidates.append(row)

    rejection_reasons: Counter[str] = Counter()
    accepted_hits = 0
    rejected = 0
    review = 0
    gate_events = 0

    print("=== OFFLINE REPLAY (historical DB) ===")
    print(f"classifier_name={CLASSIFIER_NAME}")
    print(f"classifier_version={CLASSIFIER_VERSION}")
    print(f"taxonomy_version={TAXONOMY_VERSION}")
    print(f"candidate_transcripts={len(candidates)}")
    print()

    for row in candidates:
        text = row["text"]
        matches = find_keyword_matches(text, keywords, min_record_confidence=0.6)
        if not matches:
            continue
        gate_events += 1
        gate = gate_keyword_matches_for_persistence(text, matches)
        cls = gate.classification
        if cls is None:
            continue
        extra = classification_log_extra(cls)
        status = extra.get("classification_status")
        reason = extra.get("classification_reason")
        if gate.persisted:
            accepted_hits += len(gate.matches)
        elif status == "review":
            review += 1
        else:
            rejected += 1
            rejection_reasons[str(reason)] += 1

        snippet = text[:200].replace("\n", " ")
        print(
            f"chunk_id={row['id']} station={row['station']} "
            f"status={status} reason={reason} "
            f"raw_match_count={len(matches)} persisted_match_count={len(gate.matches)}"
        )
        print(f"  snippet: {snippet}")
        print()

    print("=== SUMMARY ===")
    print(f"target_phrase_matches={gate_events}")
    print(f"accepted_keyword_hits={accepted_hits}")
    print(f"rejected_after_classifier={rejected}")
    print(f"review_after_classifier_not_persisted={review}")
    print(f"top_rejection_reasons={dict(rejection_reasons.most_common(8))}")
    conn.close()


if __name__ == "__main__":
    main()
