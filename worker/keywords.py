"""Loan keyword scanning for transcript keyword-hit statistics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from shared.models import LoanKeywordEntry

DEFAULT_MIN_RECORD_CONFIDENCE = 0.6


@dataclass(frozen=True)
class KeywordMatch:
    keyword: str
    excerpt: str
    confidence: float


def find_keyword_matches(
    transcript: str,
    keywords: list[LoanKeywordEntry] | list[str],
    *,
    excerpt_radius: int = 50,
    min_record_confidence: float = DEFAULT_MIN_RECORD_CONFIDENCE,
) -> list[KeywordMatch]:
    """Return phrase matches in transcript (case-insensitive, longest phrase first)."""
    if not transcript or not keywords:
        return []

    entries: list[LoanKeywordEntry] = []
    for item in keywords:
        if isinstance(item, str):
            phrase = item.strip()
            if phrase:
                entries.append(LoanKeywordEntry(phrase=phrase, confidence=0.7))
        else:
            entries.append(item)

    lowered = transcript.lower()
    matches: list[KeywordMatch] = []
    seen: set[str] = set()

    for entry in sorted(entries, key=lambda e: len(e.phrase), reverse=True):
        phrase = entry.phrase.strip()
        if not phrase or entry.confidence < min_record_confidence:
            continue
        needle = phrase.lower()
        if needle in seen:
            continue
        index = lowered.find(needle)
        if index < 0:
            continue
        seen.add(needle)
        start = max(index - excerpt_radius, 0)
        end = min(index + len(needle) + excerpt_radius, len(transcript))
        excerpt_body = transcript[start:end].strip()
        if start > 0:
            excerpt_body = f"...{excerpt_body}"
        if end < len(transcript):
            excerpt_body = f"{excerpt_body}..."
        excerpt = f"[confidence={entry.confidence:.2f}] {excerpt_body}"
        matches.append(
            KeywordMatch(keyword=phrase, excerpt=excerpt, confidence=entry.confidence)
        )

    return matches


def record_keyword_hits(
    conn: sqlite3.Connection,
    *,
    station_id: int,
    chunk_id: int,
    hit_ts: float,
    matches: list[KeywordMatch],
    detection_id: int | None = None,
) -> int:
    """Insert keyword hit rows; ignore duplicate (chunk_id, keyword) pairs."""
    inserted = 0
    for match in matches:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO keyword_hits (
                station_id, keyword, chunk_id, detection_id, hit_ts, context_excerpt
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                station_id,
                match.keyword,
                chunk_id,
                detection_id,
                hit_ts,
                match.excerpt,
            ),
        )
        inserted += cursor.rowcount
    return inserted
