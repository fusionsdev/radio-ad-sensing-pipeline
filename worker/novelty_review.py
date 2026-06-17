"""Dashboard review actions for novelty opportunities and candidates."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from shared.db import get_connection, retry_on_busy, transaction

ACTIVE_OPPORTUNITY_STATUSES = frozenset({"new", "approved"})


class ReviewError(LookupError):
    """Raised when a review target does not exist or is invalid."""


def _write_audit(
    conn: sqlite3.Connection,
    *,
    target_type: str,
    target_id: int,
    action: str,
    old_status: str | None,
    new_status: str | None,
    reason: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO novelty_review_actions (
            target_type, target_id, action, old_status, new_status, reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (target_type, target_id, action, old_status, new_status, reason, time.time()),
    )


def _latest_novelty_result(
    conn: sqlite3.Connection,
    *,
    candidate_id: int | None = None,
    novelty_result_id: int | None = None,
) -> sqlite3.Row:
    if novelty_result_id is not None:
        row = conn.execute(
            "SELECT * FROM novelty_results WHERE id = ?",
            (novelty_result_id,),
        ).fetchone()
    elif candidate_id is not None:
        row = conn.execute(
            """
            SELECT * FROM novelty_results
            WHERE candidate_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
    else:
        raise ReviewError("candidate_id or novelty_result_id is required")

    if row is None:
        raise ReviewError("novelty result not found")
    return row


def _sync_opportunity_status_for_candidate(
    conn: sqlite3.Connection,
    candidate_id: int,
    new_status: str,
) -> list[tuple[int, str]]:
    rows = conn.execute(
        """
        SELECT id, status FROM keyword_opportunities
        WHERE candidate_id = ?
        """,
        (candidate_id,),
    ).fetchall()
    changes: list[tuple[int, str]] = []
    for row in rows:
        old_status = str(row["status"])
        if old_status == new_status:
            continue
        conn.execute(
            "UPDATE keyword_opportunities SET status = ? WHERE id = ?",
            (new_status, row["id"]),
        )
        changes.append((int(row["id"]), old_status))
    return changes


@retry_on_busy()
def approve_opportunity(
    db_path: str | Path,
    opportunity_id: int,
    reason: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            row = conn.execute(
                """
                SELECT id, status, candidate_id
                FROM keyword_opportunities
                WHERE id = ?
                """,
                (opportunity_id,),
            ).fetchone()
            if row is None:
                raise ReviewError(f"opportunity {opportunity_id} not found")

            old_status = str(row["status"])
            conn.execute(
                "UPDATE keyword_opportunities SET status = 'approved' WHERE id = ?",
                (opportunity_id,),
            )
            conn.execute(
                """
                UPDATE novelty_results
                SET reviewed_status = 'approved'
                WHERE candidate_id = ?
                """,
                (row["candidate_id"],),
            )
            _write_audit(
                conn,
                target_type="opportunity",
                target_id=opportunity_id,
                action="approve",
                old_status=old_status,
                new_status="approved",
                reason=reason,
            )
    finally:
        conn.close()


@retry_on_busy()
def reject_opportunity(
    db_path: str | Path,
    opportunity_id: int,
    reason: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            row = conn.execute(
                """
                SELECT id, status, candidate_id
                FROM keyword_opportunities
                WHERE id = ?
                """,
                (opportunity_id,),
            ).fetchone()
            if row is None:
                raise ReviewError(f"opportunity {opportunity_id} not found")

            old_status = str(row["status"])
            conn.execute(
                "UPDATE keyword_opportunities SET status = 'rejected' WHERE id = ?",
                (opportunity_id,),
            )
            conn.execute(
                """
                UPDATE novelty_results
                SET reviewed_status = 'rejected', report_eligible = 0
                WHERE candidate_id = ?
                """,
                (row["candidate_id"],),
            )
            _write_audit(
                conn,
                target_type="opportunity",
                target_id=opportunity_id,
                action="reject",
                old_status=old_status,
                new_status="rejected",
                reason=reason,
            )
    finally:
        conn.close()


@retry_on_busy()
def mark_noise(
    db_path: str | Path,
    *,
    candidate_id: int | None = None,
    novelty_result_id: int | None = None,
    reason: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            row = _latest_novelty_result(
                conn,
                candidate_id=candidate_id,
                novelty_result_id=novelty_result_id,
            )
            old_reviewed = str(row["reviewed_status"])
            conn.execute(
                """
                UPDATE novelty_results
                SET novelty_status = 'noise',
                    reviewed_status = 'noise',
                    report_eligible = 0,
                    report_suppressed_reason = 'manual_noise'
                WHERE id = ?
                """,
                (row["id"],),
            )
            for opp_id, opp_old in _sync_opportunity_status_for_candidate(
                conn, int(row["candidate_id"]), "noise"
            ):
                _write_audit(
                    conn,
                    target_type="opportunity",
                    target_id=opp_id,
                    action="mark_noise",
                    old_status=opp_old,
                    new_status="noise",
                    reason=reason,
                )
            _write_audit(
                conn,
                target_type="novelty_result",
                target_id=int(row["id"]),
                action="mark_noise",
                old_status=old_reviewed,
                new_status="noise",
                reason=reason,
            )
    finally:
        conn.close()


@retry_on_busy()
def archive_item(
    db_path: str | Path,
    target_type: str,
    target_id: int,
    reason: str | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            if target_type == "opportunity":
                row = conn.execute(
                    """
                    SELECT id, status, candidate_id
                    FROM keyword_opportunities
                    WHERE id = ?
                    """,
                    (target_id,),
                ).fetchone()
                if row is None:
                    raise ReviewError(f"opportunity {target_id} not found")
                old_status = str(row["status"])
                conn.execute(
                    "UPDATE keyword_opportunities SET status = 'archived' WHERE id = ?",
                    (target_id,),
                )
                nr = _latest_novelty_result(conn, candidate_id=int(row["candidate_id"]))
                old_reviewed = str(nr["reviewed_status"])
                conn.execute(
                    """
                    UPDATE novelty_results
                    SET reviewed_status = 'archived', report_eligible = 0
                    WHERE id = ?
                    """,
                    (nr["id"],),
                )
                _write_audit(
                    conn,
                    target_type="opportunity",
                    target_id=target_id,
                    action="archive",
                    old_status=old_status,
                    new_status="archived",
                    reason=reason,
                )
                _write_audit(
                    conn,
                    target_type="novelty_result",
                    target_id=int(nr["id"]),
                    action="archive",
                    old_status=old_reviewed,
                    new_status="archived",
                    reason=reason,
                )
            elif target_type == "novelty_result":
                row = _latest_novelty_result(conn, novelty_result_id=target_id)
                old_reviewed = str(row["reviewed_status"])
                conn.execute(
                    """
                    UPDATE novelty_results
                    SET reviewed_status = 'archived', report_eligible = 0
                    WHERE id = ?
                    """,
                    (target_id,),
                )
                for opp_id, opp_old in _sync_opportunity_status_for_candidate(
                    conn, int(row["candidate_id"]), "archived"
                ):
                    _write_audit(
                        conn,
                        target_type="opportunity",
                        target_id=opp_id,
                        action="archive",
                        old_status=opp_old,
                        new_status="archived",
                        reason=reason,
                    )
                _write_audit(
                    conn,
                    target_type="novelty_result",
                    target_id=target_id,
                    action="archive",
                    old_status=old_reviewed,
                    new_status="archived",
                    reason=reason,
                )
            else:
                raise ReviewError(f"unsupported target_type: {target_type}")
    finally:
        conn.close()


@retry_on_busy()
def add_to_known_pending(
    db_path: str | Path,
    term: str,
    term_type: str,
    vertical: str | None,
    source_candidate_id: int,
    reason: str | None = None,
) -> int:
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            candidate = conn.execute(
                "SELECT id FROM candidate_terms WHERE id = ?",
                (source_candidate_id,),
            ).fetchone()
            if candidate is None:
                raise ReviewError(f"candidate {source_candidate_id} not found")

            cursor = conn.execute(
                """
                INSERT INTO known_terms_pending (
                    term, term_type, vertical, reason, source_candidate_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (term.strip(), term_type.strip(), vertical, reason, source_candidate_id, time.time()),
            )
            pending_id = int(cursor.lastrowid)

            nr = _latest_novelty_result(conn, candidate_id=source_candidate_id)
            old_reviewed = str(nr["reviewed_status"])
            conn.execute(
                """
                UPDATE novelty_results
                SET reviewed_status = 'known_pending', report_eligible = 0
                WHERE id = ?
                """,
                (nr["id"],),
            )
            _write_audit(
                conn,
                target_type="known_terms_pending",
                target_id=pending_id,
                action="add_to_known_pending",
                old_status=None,
                new_status="pending",
                reason=reason,
            )
            _write_audit(
                conn,
                target_type="novelty_result",
                target_id=int(nr["id"]),
                action="add_to_known_pending",
                old_status=old_reviewed,
                new_status="known_pending",
                reason=reason,
            )
            return pending_id
    finally:
        conn.close()
