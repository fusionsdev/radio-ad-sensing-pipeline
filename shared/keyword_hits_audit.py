"""Audit legacy keyword_hits rows for pre-rollout vertical pollution."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from shared.consumer_personal_loan import (
    CLASSIFIER_VERSION,
    load_consumer_personal_loan_taxonomy,
)
from shared.verticals import keyword_to_vertical_map, load_vertical_keywords

# Explicit legacy phrases from pre-consumer_personal_loan vertical configs.
LEGACY_POLLUTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "tax relief",
        "tax debt",
        "back taxes",
        "unfiled tax returns",
        "stop collections",
        "term life insurance",
        "life insurance",
        "business funding",
        "business loan",
        "merchant cash advance",
        "working capital",
        "mortgage refinance",
        "refinance mortgage",
        "cash-out refinance",
        "auto loan",
        "car loan",
        "student loan",
        "debt relief",
        "debt consolidation",
        "credit repair",
        "timeshare exit",
        "maintenance fees",
        "loan",
    }
)

POLLUTED_SUBSTRINGS: tuple[str, ...] = (
    "tax",
    "irs",
    "back tax",
    "insurance",
    "business loan",
    "business funding",
    "merchant cash advance",
    "working capital",
    "mortgage",
    "refinance",
    "auto loan",
    "car loan",
    "student loan",
    "debt relief",
    "debt settlement",
    "credit repair",
    "timeshare",
    "wage garnishment",
)


@dataclass(frozen=True)
class KeywordHitAuditRow:
    keyword: str
    hit_count: int
    vertical: str | None
    flags: tuple[str, ...]


@dataclass
class KeywordHitsAuditReport:
    total_rows: int
    unique_keywords: int
    rows: list[KeywordHitAuditRow] = field(default_factory=list)
    polluted_row_count: int = 0
    legacy_non_target_count: int = 0
    clean_consumer_loan_count: int = 0

    @property
    def polluted_keywords(self) -> list[KeywordHitAuditRow]:
        return [row for row in self.rows if row.flags]

    def summary_lines(self) -> list[str]:
        lines = [
            f"keyword_hits audit (classifier {CLASSIFIER_VERSION})",
            f"  total rows: {self.total_rows}",
            f"  unique keywords: {self.unique_keywords}",
            f"  polluted rows: {self.polluted_row_count}",
            f"  legacy non-target rows: {self.legacy_non_target_count}",
            f"  clean consumer_personal_loan rows: {self.clean_consumer_loan_count}",
            "",
            "Flagged keywords:",
        ]
        if not self.polluted_keywords:
            lines.append("  (none)")
        for row in self.polluted_keywords:
            flags = ", ".join(row.flags)
            vertical = row.vertical or "unknown"
            lines.append(
                f"  {row.hit_count:5d}  {row.keyword!r}  vertical={vertical}  [{flags}]"
            )
        return lines


def _keyword_vertical(keyword: str, vertical_map: dict[str, str]) -> str | None:
    return vertical_map.get(keyword.lower())


def _audit_flags(
    keyword: str,
    *,
    vertical: str | None,
    target_phrases: set[str],
    excluded_phrases: set[str],
) -> tuple[str, ...]:
    lowered = keyword.lower()
    flags: list[str] = []

    if lowered in LEGACY_POLLUTED_KEYWORDS:
        flags.append("legacy_polluted_keyword")

    if any(sub in lowered for sub in POLLUTED_SUBSTRINGS):
        if lowered not in target_phrases:
            flags.append("polluted_substring")

    if lowered in excluded_phrases:
        flags.append("taxonomy_excluded")

    if vertical and vertical != "consumer_personal_loan":
        flags.append(f"legacy_vertical:{vertical}")

    if lowered not in target_phrases and "legacy_polluted_keyword" not in flags:
        if not flags:
            flags.append("non_target_keyword")

    if lowered in target_phrases and not flags:
        return ()

    if lowered in target_phrases and flags:
        # Target phrase stored from polluted transcript context — still flag.
        flags.append("target_keyword_polluted_context")

    return tuple(dict.fromkeys(flags))


def audit_keyword_hits(conn: sqlite3.Connection) -> KeywordHitsAuditReport:
    """Summarize keyword_hits and flag legacy / polluted entries."""
    vertical_map = keyword_to_vertical_map(load_vertical_keywords())
    taxonomy = load_consumer_personal_loan_taxonomy()
    target_phrases = {p.lower() for p in taxonomy.target_phrases}
    excluded_phrases = {p.lower() for p in taxonomy.excluded_phrases}

    total_rows = conn.execute("SELECT COUNT(*) FROM keyword_hits").fetchone()[0]
    grouped = conn.execute(
        """
        SELECT keyword, COUNT(*) AS hit_count
        FROM keyword_hits
        GROUP BY keyword
        ORDER BY hit_count DESC, keyword
        """
    ).fetchall()

    report = KeywordHitsAuditReport(
        total_rows=int(total_rows),
        unique_keywords=len(grouped),
    )

    for row in grouped:
        keyword = str(row["keyword"])
        hit_count = int(row["hit_count"])
        vertical = _keyword_vertical(keyword, vertical_map)
        flags = _audit_flags(
            keyword,
            vertical=vertical,
            target_phrases=target_phrases,
            excluded_phrases=excluded_phrases,
        )
        audit_row = KeywordHitAuditRow(
            keyword=keyword,
            hit_count=hit_count,
            vertical=vertical,
            flags=flags,
        )
        report.rows.append(audit_row)
        if flags:
            report.polluted_row_count += hit_count
            if "non_target_keyword" in flags:
                report.legacy_non_target_count += hit_count
        elif vertical == "consumer_personal_loan" or keyword.lower() in target_phrases:
            report.clean_consumer_loan_count += hit_count

    return report


def apply_keyword_hits_cleanup(
    conn: sqlite3.Connection,
    report: KeywordHitsAuditReport,
    *,
    apply: bool = False,
) -> tuple[int, list[str]]:
    """Delete polluted keyword_hits rows. Default dry-run returns SQL only."""
    polluted = report.polluted_keywords
    if not polluted:
        return 0, ["No polluted keyword_hits rows to remove."]

    keywords = [row.keyword for row in polluted]
    placeholders = ", ".join("?" for _ in keywords)
    sql = f"DELETE FROM keyword_hits WHERE keyword IN ({placeholders})"
    messages = [
        f"Would delete {report.polluted_row_count} rows across {len(keywords)} keywords.",
        f"SQL: {sql}",
        f"Params: {keywords}",
    ]

    if not apply:
        messages.insert(0, "DRY RUN — no rows deleted.")
        return 0, messages

    cursor = conn.execute(sql, keywords)
    deleted = int(cursor.rowcount)
    messages.insert(0, f"APPLIED — deleted {deleted} keyword_hits rows.")
    return deleted, messages
