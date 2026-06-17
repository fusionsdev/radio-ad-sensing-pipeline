"""Dashboard queries for novelty-first keyword discovery."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from shared.db import get_connection
from worker.batch_validation import SCORE_BUCKET_LABELS


@dataclass(frozen=True)
class NoveltyRow:
    id: int
    candidate_id: int
    candidate_text: str
    candidate_type: str
    vertical: str | None
    sub_vertical: str | None
    novelty_status: str
    novelty_score: float
    opportunity_score: float
    source_type: str
    source_url: str | None
    evidence_text: str | None
    known_match: str | None
    report_suppressed_reason: str | None
    report_eligible: bool
    reviewed_status: str
    created_at: float
    opportunity_id: int | None = None
    opportunity_status: str | None = None


@dataclass(frozen=True)
class OpportunityRow:
    id: int
    candidate_id: int
    opportunity_text: str
    opportunity_type: str
    vertical: str | None
    sub_vertical: str | None
    source_type: str
    source_url: str | None
    evidence_text: str | None
    novelty_score: float
    opportunity_score: float
    risk_level: str
    suggested_action: str | None
    status: str
    created_at: float


@dataclass(frozen=True)
class KnownTermPendingRow:
    id: int
    term: str
    term_type: str
    vertical: str | None
    reason: str | None
    source_candidate_id: int | None
    status: str
    created_at: float


@dataclass(frozen=True)
class NoveltyOverview:
    total: int
    report_eligible: int
    new_count: int
    known_count: int
    noise_count: int
    opportunities: int


@dataclass(frozen=True)
class BatchReviewView:
    batch_id: str | None
    batch_imported_at: float | None
    total: int
    report_eligible: int
    status_counts: dict[str, int]
    suppression_counts: dict[str, int]
    score_distribution: dict[str, int]
    report_eligible_rows: tuple[NoveltyRow, ...]
    grouped_by_status: dict[str, tuple[NoveltyRow, ...]] = field(default_factory=dict)


def _novelty_tables_exist(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name IN ('novelty_results', 'candidate_terms', 'keyword_opportunities')
        """
    ).fetchone()
    return bool(row and row[0] == 3)


def fetch_novelty_overview(db_path: Path) -> NoveltyOverview:
    conn = get_connection(db_path, read_only=True)
    try:
        if not _novelty_tables_exist(conn):
            return NoveltyOverview(0, 0, 0, 0, 0, 0)
        total = conn.execute("SELECT COUNT(*) FROM novelty_results").fetchone()[0]
        report_eligible = conn.execute(
            "SELECT COUNT(*) FROM novelty_results WHERE report_eligible = 1"
        ).fetchone()[0]
        new_count = conn.execute(
            """
            SELECT COUNT(*) FROM novelty_results
            WHERE novelty_status IN ('new', 'needs_review')
            """
        ).fetchone()[0]
        known_count = conn.execute(
            """
            SELECT COUNT(*) FROM novelty_results
            WHERE novelty_status IN ('known_duplicate', 'near_duplicate', 'generic')
            """
        ).fetchone()[0]
        noise_count = conn.execute(
            """
            SELECT COUNT(*) FROM novelty_results
            WHERE novelty_status IN ('noise', 'weak_evidence', 'excluded_vertical')
            """
        ).fetchone()[0]
        opportunities = conn.execute(
            "SELECT COUNT(*) FROM keyword_opportunities WHERE status = 'new'"
        ).fetchone()[0]
        return NoveltyOverview(
            total=int(total),
            report_eligible=int(report_eligible),
            new_count=int(new_count),
            known_count=int(known_count),
            noise_count=int(noise_count),
            opportunities=int(opportunities),
        )
    finally:
        conn.close()


def _row_to_novelty(row: sqlite3.Row) -> NoveltyRow:
    return NoveltyRow(
        id=int(row["id"]),
        candidate_id=int(row["candidate_id"]),
        candidate_text=str(row["candidate_text"]),
        candidate_type=str(row["candidate_type"] or ""),
        vertical=row["vertical"],
        sub_vertical=row["sub_vertical"],
        novelty_status=str(row["novelty_status"]),
        novelty_score=float(row["novelty_score"]),
        opportunity_score=float(row["opportunity_score"]),
        source_type=str(row["source_type"] or ""),
        source_url=row["source_url"],
        evidence_text=row["evidence_text"],
        known_match=row["known_match"],
        report_suppressed_reason=row["report_suppressed_reason"],
        report_eligible=bool(row["report_eligible"]),
        reviewed_status=str(row["reviewed_status"]),
        created_at=float(row["created_at"]),
        opportunity_id=int(row["opportunity_id"]) if row["opportunity_id"] is not None else None,
        opportunity_status=row["opportunity_status"],
    )


_NOVELTY_SELECT = """
SELECT
    nr.id,
    nr.candidate_id,
    ct.candidate_text,
    ct.candidate_type,
    ct.vertical,
    ct.sub_vertical,
    nr.novelty_status,
    nr.novelty_score,
    nr.opportunity_score,
    ct.source_type,
    ct.source_url,
    ct.evidence_text,
    nr.known_match,
    nr.report_suppressed_reason,
    nr.report_eligible,
    nr.reviewed_status,
    nr.created_at,
    ko.id AS opportunity_id,
    ko.status AS opportunity_status
FROM novelty_results nr
JOIN candidate_terms ct ON ct.id = nr.candidate_id
LEFT JOIN raw_discovery_items r ON r.id = ct.raw_item_id
LEFT JOIN keyword_opportunities ko ON ko.candidate_id = ct.id
"""


def fetch_novelty_results(
    db_path: Path,
    *,
    status_filter: str | None = None,
    report_eligible_only: bool = False,
    limit: int = 200,
) -> list[NoveltyRow]:
    conn = get_connection(db_path, read_only=True)
    try:
        if not _novelty_tables_exist(conn):
            return []
        clauses: list[str] = []
        params: list[object] = []
        if status_filter == "new":
            clauses.append("nr.novelty_status IN ('new', 'needs_review')")
        elif status_filter == "known":
            clauses.append(
                "nr.novelty_status IN ('known_duplicate', 'near_duplicate', 'generic')"
            )
        elif status_filter == "noise":
            clauses.append(
                "nr.novelty_status IN ('noise', 'weak_evidence', 'excluded_vertical')"
            )
        if report_eligible_only:
            clauses.append("nr.report_eligible = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""
            {_NOVELTY_SELECT}
            {where}
            ORDER BY nr.created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [_row_to_novelty(row) for row in rows]
    finally:
        conn.close()


def fetch_keyword_opportunities(db_path: Path, *, limit: int = 200) -> list[OpportunityRow]:
    conn = get_connection(db_path, read_only=True)
    try:
        if not _novelty_tables_exist(conn):
            return []
        rows = conn.execute(
            """
            SELECT
                id, candidate_id, opportunity_text, opportunity_type, vertical,
                sub_vertical, source_type, source_url, evidence_text,
                novelty_score, opportunity_score, risk_level, suggested_action,
                status, created_at
            FROM keyword_opportunities
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            OpportunityRow(
                id=int(row["id"]),
                candidate_id=int(row["candidate_id"]),
                opportunity_text=str(row["opportunity_text"]),
                opportunity_type=str(row["opportunity_type"]),
                vertical=row["vertical"],
                sub_vertical=row["sub_vertical"],
                source_type=str(row["source_type"]),
                source_url=row["source_url"],
                evidence_text=row["evidence_text"],
                novelty_score=float(row["novelty_score"]),
                opportunity_score=float(row["opportunity_score"]),
                risk_level=str(row["risk_level"]),
                suggested_action=row["suggested_action"],
                status=str(row["status"]),
                created_at=float(row["created_at"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def fetch_novelty_result_detail(
    db_path: Path,
    novelty_result_id: int,
) -> tuple[str, str, str | None, int] | None:
    """Return candidate_text, candidate_type, vertical, candidate_id for a novelty result."""
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT ct.candidate_text, ct.candidate_type, ct.vertical, ct.id AS candidate_id
            FROM novelty_results nr
            JOIN candidate_terms ct ON ct.id = nr.candidate_id
            WHERE nr.id = ?
            """,
            (novelty_result_id,),
        ).fetchone()
        if row is None:
            return None
        return (
            str(row["candidate_text"]),
            str(row["candidate_type"]),
            row["vertical"],
            int(row["candidate_id"]),
        )
    finally:
        conn.close()


def fetch_known_terms_pending(db_path: Path, *, limit: int = 200) -> list[KnownTermPendingRow]:
    conn = get_connection(db_path, read_only=True)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='known_terms_pending'"
        ).fetchone()
        if row is None:
            return []
        rows = conn.execute(
            """
            SELECT id, term, term_type, vertical, reason, source_candidate_id, status, created_at
            FROM known_terms_pending
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            KnownTermPendingRow(
                id=int(item["id"]),
                term=str(item["term"]),
                term_type=str(item["term_type"]),
                vertical=item["vertical"],
                reason=item["reason"],
                source_candidate_id=item["source_candidate_id"],
                status=str(item["status"]),
                created_at=float(item["created_at"]),
            )
            for item in rows
        ]
    finally:
        conn.close()


def _score_bucket(score: float) -> str:
    if score <= 20:
        return "0-20"
    if score <= 40:
        return "21-40"
    if score <= 60:
        return "41-60"
    if score <= 80:
        return "61-80"
    return "81-100"


def _fetch_latest_batch_id(conn: sqlite3.Connection) -> tuple[str | None, float | None]:
    row = conn.execute(
        """
        SELECT json_extract(raw_json, '$.batch_id') AS batch_id, MAX(created_at) AS latest
        FROM raw_discovery_items
        WHERE json_extract(raw_json, '$.batch_id') IS NOT NULL
        GROUP BY batch_id
        ORDER BY latest DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None or row["batch_id"] is None:
        return None, None
    return str(row["batch_id"]), float(row["latest"])


def fetch_batch_review(db_path: Path, *, batch_id: str | None = None) -> BatchReviewView:
    """Load novelty results for the latest (or selected) import batch."""
    conn = get_connection(db_path, read_only=True)
    try:
        if not _novelty_tables_exist(conn):
            return BatchReviewView(
                batch_id=None,
                batch_imported_at=None,
                total=0,
                report_eligible=0,
                status_counts={},
                suppression_counts={},
                score_distribution={label: 0 for label in SCORE_BUCKET_LABELS},
                report_eligible_rows=(),
            )

        resolved_batch_id = batch_id
        batch_imported_at: float | None = None
        if resolved_batch_id is None:
            resolved_batch_id, batch_imported_at = _fetch_latest_batch_id(conn)
        else:
            row = conn.execute(
                """
                SELECT MAX(created_at) AS latest
                FROM raw_discovery_items
                WHERE json_extract(raw_json, '$.batch_id') = ?
                """,
                (resolved_batch_id,),
            ).fetchone()
            if row and row["latest"] is not None:
                batch_imported_at = float(row["latest"])

        if resolved_batch_id is None:
            rows = fetch_novelty_results(db_path, limit=500)
        else:
            db_rows = conn.execute(
                f"""
                {_NOVELTY_SELECT}
                WHERE json_extract(r.raw_json, '$.batch_id') = ?
                ORDER BY nr.created_at DESC
                """,
                (resolved_batch_id,),
            ).fetchall()
            rows = [_row_to_novelty(row) for row in db_rows]

        status_counts = Counter(row.novelty_status for row in rows)
        suppression_counts = Counter(
            row.report_suppressed_reason
            for row in rows
            if row.report_suppressed_reason and not row.report_eligible
        )
        score_distribution = Counter(_score_bucket(row.novelty_score) for row in rows)
        grouped: dict[str, list[NoveltyRow]] = {}
        for row in rows:
            grouped.setdefault(row.novelty_status, []).append(row)

        eligible = tuple(row for row in rows if row.report_eligible)
        return BatchReviewView(
            batch_id=resolved_batch_id,
            batch_imported_at=batch_imported_at,
            total=len(rows),
            report_eligible=len(eligible),
            status_counts=dict(sorted(status_counts.items())),
            suppression_counts=dict(sorted(suppression_counts.items())),
            score_distribution={
                label: score_distribution.get(label, 0) for label in SCORE_BUCKET_LABELS
            },
            report_eligible_rows=eligible,
            grouped_by_status={key: tuple(values) for key, values in sorted(grouped.items())},
        )
    finally:
        conn.close()


def load_batch_meta(imports_dir: Path, batch_id: str) -> dict[str, object] | None:
    meta_path = imports_dir / f"{batch_id}.meta.json"
    if not meta_path.is_file():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class LandingPageSummaryRow:
    url: str
    title: str | None
    vertical: str | None
    candidate_count: int
    report_eligible_count: int
    suppressed_count: int
    imported_at: float


@dataclass(frozen=True)
class LandingPageCandidateRow:
    url: str
    candidate_text: str
    candidate_type: str
    vertical: str | None
    novelty_status: str
    novelty_score: float
    opportunity_score: float
    report_eligible: bool
    suppression_reason: str | None
    evidence_text: str | None


@dataclass(frozen=True)
class LandingPageSourceView:
    pages_imported: int
    candidates_extracted: int
    report_eligible: int
    suppressed: int
    top_opportunities: tuple[LandingPageCandidateRow, ...]
    pages: tuple[LandingPageSummaryRow, ...]
    recent_candidates: tuple[LandingPageCandidateRow, ...]


def fetch_landing_page_source_view(db_path: Path, *, limit: int = 100) -> LandingPageSourceView:
    conn = get_connection(db_path, read_only=True)
    try:
        if not _novelty_tables_exist(conn):
            return LandingPageSourceView(0, 0, 0, 0, (), (), ())

        page_rows = conn.execute(
            """
            SELECT
                COALESCE(r.source_url, json_extract(r.raw_json, '$.url')) AS url,
                r.title,
                json_extract(r.raw_json, '$.vertical') AS vertical,
                r.created_at,
                COUNT(DISTINCT ct.id) AS candidate_count,
                SUM(CASE WHEN nr.report_eligible = 1 THEN 1 ELSE 0 END) AS report_eligible_count,
                SUM(CASE WHEN nr.report_eligible = 0 THEN 1 ELSE 0 END) AS suppressed_count
            FROM raw_discovery_items r
            LEFT JOIN candidate_terms ct ON ct.raw_item_id = r.id
            LEFT JOIN novelty_results nr ON nr.candidate_id = ct.id
            WHERE r.source_type = 'landing_page'
            GROUP BY r.id
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        candidate_rows = conn.execute(
            """
            SELECT
                COALESCE(r.source_url, ct.source_url) AS url,
                ct.candidate_text,
                ct.candidate_type,
                ct.vertical,
                nr.novelty_status,
                nr.novelty_score,
                nr.opportunity_score,
                nr.report_eligible,
                nr.report_suppressed_reason,
                ct.evidence_text
            FROM candidate_terms ct
            JOIN raw_discovery_items r ON r.id = ct.raw_item_id
            JOIN novelty_results nr ON nr.candidate_id = ct.id
            WHERE ct.source_type = 'landing_page'
            ORDER BY nr.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    pages = tuple(
        LandingPageSummaryRow(
            url=str(row["url"] or ""),
            title=row["title"],
            vertical=row["vertical"],
            candidate_count=int(row["candidate_count"] or 0),
            report_eligible_count=int(row["report_eligible_count"] or 0),
            suppressed_count=int(row["suppressed_count"] or 0),
            imported_at=float(row["created_at"]),
        )
        for row in page_rows
    )
    candidates = tuple(
        LandingPageCandidateRow(
            url=str(row["url"] or ""),
            candidate_text=str(row["candidate_text"]),
            candidate_type=str(row["candidate_type"] or ""),
            vertical=row["vertical"],
            novelty_status=str(row["novelty_status"]),
            novelty_score=float(row["novelty_score"]),
            opportunity_score=float(row["opportunity_score"]),
            report_eligible=bool(row["report_eligible"]),
            suppression_reason=row["report_suppressed_reason"],
            evidence_text=row["evidence_text"],
        )
        for row in candidate_rows
    )
    eligible = tuple(row for row in candidates if row.report_eligible)
    top = tuple(
        sorted(eligible, key=lambda row: (row.opportunity_score, row.novelty_score), reverse=True)[:10]
    )
    return LandingPageSourceView(
        pages_imported=len(pages),
        candidates_extracted=len(candidates),
        report_eligible=len(eligible),
        suppressed=len(candidates) - len(eligible),
        top_opportunities=top,
        pages=pages,
        recent_candidates=candidates,
    )
