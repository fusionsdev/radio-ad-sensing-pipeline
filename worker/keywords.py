"""Loan keyword scanning for transcript keyword-hit statistics."""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache

from shared.models import LoanKeywordEntry

logger = logging.getLogger(__name__)

DEFAULT_MIN_RECORD_CONFIDENCE = 0.6


@lru_cache(maxsize=1024)
def _phrase_pattern(needle: str) -> re.Pattern[str]:
    """Compile a word-boundary, whitespace-tolerant matcher for *needle*.

    Uses lookarounds instead of ``\\b`` so phrases bounded by non-word characters
    (e.g. ``cash-out refinance``) still anchor correctly, and collapses internal
    whitespace so ASR spacing variance does not cause misses. Word boundaries stop
    substring false positives such as ``loan`` matching inside ``balloon`` or
    ``heloc`` inside a larger token.
    """
    tokens = [re.escape(token) for token in needle.split()]
    body = r"\s+".join(tokens) if tokens else re.escape(needle)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


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
        if not phrase:
            continue
        if entry.confidence < min_record_confidence:
            logger.debug(
                "Skipping keyword %r: confidence %.2f < min_record_confidence %.2f",
                phrase,
                entry.confidence,
                min_record_confidence,
            )
            continue
        needle = phrase.lower()
        if needle in seen:
            continue
        found = _phrase_pattern(needle).search(lowered)
        if found is None:
            continue
        seen.add(needle)
        index = found.start()
        match_end = found.end()
        start = max(index - excerpt_radius, 0)
        end = min(match_end + excerpt_radius, len(transcript))
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
