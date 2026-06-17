"""Tests for novelty dashboard review actions."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alerter.novelty_reporter import fetch_pending_opportunities, format_pending_digest
from dashboard.main import create_app
from shared.db import get_connection, migrate
from worker.novelty_engine import CandidateInput, process_candidate
from worker.novelty_review import (
    ReviewError,
    add_to_known_pending,
    approve_opportunity,
    archive_item,
    mark_noise,
    reject_opportunity,
)


@pytest.fixture
def novelty_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "review.db"
    migrate(db_path)
    return db_path


def _seed_opportunity(db_path: Path) -> tuple[int, int, int]:
    _, evaluation = process_candidate(
        db_path,
        CandidateInput(
            candidate_text="dog ACL surgery payment plan",
            vertical="pet_financing",
            source_type="manual",
            source_url="https://example.com/1",
            evidence_text="Payment plan discussion",
            source_confidence=0.85,
        ),
    )
    assert evaluation.report_eligible is True
    conn = get_connection(db_path)
    try:
        opp_id = conn.execute(
            "SELECT id FROM keyword_opportunities ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        candidate_id = conn.execute(
            "SELECT id FROM candidate_terms ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        novelty_id = conn.execute(
            "SELECT id FROM novelty_results ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    return int(opp_id), int(candidate_id), int(novelty_id)


def _audit_count(db_path: Path, *, action: str | None = None) -> int:
    conn = get_connection(db_path)
    try:
        if action is None:
            return int(conn.execute("SELECT COUNT(*) FROM novelty_review_actions").fetchone()[0])
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM novelty_review_actions WHERE action = ?",
                (action,),
            ).fetchone()[0]
        )
    finally:
        conn.close()


def test_approve_opportunity(novelty_db: Path) -> None:
    opp_id, _, _ = _seed_opportunity(novelty_db)
    before = _audit_count(novelty_db)
    approve_opportunity(novelty_db, opp_id, reason="looks good")
    conn = get_connection(novelty_db)
    try:
        status = conn.execute(
            "SELECT status FROM keyword_opportunities WHERE id = ?",
            (opp_id,),
        ).fetchone()[0]
        reviewed = conn.execute(
            """
            SELECT reviewed_status FROM novelty_results
            WHERE candidate_id = (
                SELECT candidate_id FROM keyword_opportunities WHERE id = ?
            )
            """,
            (opp_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert status == "approved"
    assert reviewed == "approved"
    assert _audit_count(novelty_db) == before + 1


def test_reject_opportunity(novelty_db: Path) -> None:
    opp_id, _, _ = _seed_opportunity(novelty_db)
    reject_opportunity(novelty_db, opp_id, reason="not relevant")
    conn = get_connection(novelty_db)
    try:
        status = conn.execute(
            "SELECT status FROM keyword_opportunities WHERE id = ?",
            (opp_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert status == "rejected"
    assert _audit_count(novelty_db, action="reject") == 1


def test_mark_noise(novelty_db: Path) -> None:
    opp_id, candidate_id, novelty_id = _seed_opportunity(novelty_db)
    mark_noise(novelty_db, novelty_result_id=novelty_id, reason="spam")
    conn = get_connection(novelty_db)
    try:
        novelty_status = conn.execute(
            "SELECT novelty_status, reviewed_status FROM novelty_results WHERE id = ?",
            (novelty_id,),
        ).fetchone()
        opp_status = conn.execute(
            "SELECT status FROM keyword_opportunities WHERE id = ?",
            (opp_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert novelty_status["novelty_status"] == "noise"
    assert novelty_status["reviewed_status"] == "noise"
    assert opp_status == "noise"
    mark_noise(novelty_db, candidate_id=candidate_id)
    assert _audit_count(novelty_db, action="mark_noise") >= 1


def test_archive_item(novelty_db: Path) -> None:
    opp_id, _, novelty_id = _seed_opportunity(novelty_db)
    archive_item(novelty_db, "opportunity", opp_id, reason="done")
    conn = get_connection(novelty_db)
    try:
        opp_status = conn.execute(
            "SELECT status FROM keyword_opportunities WHERE id = ?",
            (opp_id,),
        ).fetchone()[0]
        reviewed = conn.execute(
            "SELECT reviewed_status FROM novelty_results WHERE id = ?",
            (novelty_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert opp_status == "archived"
    assert reviewed == "archived"
    assert _audit_count(novelty_db, action="archive") >= 1


def test_add_to_known_pending(novelty_db: Path) -> None:
    _, candidate_id, novelty_id = _seed_opportunity(novelty_db)
    pending_id = add_to_known_pending(
        novelty_db,
        "dog ACL surgery payment plan",
        "generic_keyword",
        "pet_financing",
        candidate_id,
        reason="operator flagged",
    )
    conn = get_connection(novelty_db)
    try:
        pending = conn.execute(
            "SELECT term, status FROM known_terms_pending WHERE id = ?",
            (pending_id,),
        ).fetchone()
        reviewed = conn.execute(
            "SELECT reviewed_status FROM novelty_results WHERE id = ?",
            (novelty_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert pending["term"] == "dog ACL surgery payment plan"
    assert pending["status"] == "pending"
    assert reviewed == "known_pending"
    assert _audit_count(novelty_db, action="add_to_known_pending") >= 1


def test_review_error_on_missing_opportunity(novelty_db: Path) -> None:
    with pytest.raises(ReviewError):
        approve_opportunity(novelty_db, 99999)


def test_digest_excludes_rejected_noise_archived(novelty_db: Path) -> None:
    opp_id, _, novelty_id = _seed_opportunity(novelty_db)
    assert "dog ACL surgery payment plan" in format_pending_digest(novelty_db)

    reject_opportunity(novelty_db, opp_id)
    assert "dog ACL surgery payment plan" not in format_pending_digest(novelty_db)
    assert fetch_pending_opportunities(novelty_db) == []

    _, _, novelty_id2 = _seed_opportunity(novelty_db)
    mark_noise(novelty_db, novelty_result_id=novelty_id2)
    assert fetch_pending_opportunities(novelty_db) == []

    opp_id3, _, _ = _seed_opportunity(novelty_db)
    archive_item(novelty_db, "opportunity", opp_id3)
    assert fetch_pending_opportunities(novelty_db) == []


def test_digest_can_include_approved(novelty_db: Path) -> None:
    opp_id, _, _ = _seed_opportunity(novelty_db)
    approve_opportunity(novelty_db, opp_id)
    assert fetch_pending_opportunities(novelty_db) == []
    assert fetch_pending_opportunities(novelty_db, include_approved=True)


def test_dashboard_post_routes(novelty_db: Path) -> None:
    opp_id, _, novelty_id = _seed_opportunity(novelty_db)
    client = TestClient(create_app(db_path=novelty_db))

    response = client.post(
        f"/opportunities/{opp_id}/approve",
        data={"redirect": "/opportunities"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    opp_id2, _, novelty_id2 = _seed_opportunity(novelty_db)
    response = client.post(
        f"/opportunities/{opp_id2}/reject",
        data={"redirect": "/opportunities"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    opp_id3, _, novelty_id3 = _seed_opportunity(novelty_db)
    response = client.post(
        f"/novelty/{novelty_id3}/mark-noise",
        data={"redirect": "/novelty"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    opp_id4, _, novelty_id4 = _seed_opportunity(novelty_db)
    response = client.post(
        f"/novelty/{novelty_id4}/add-to-known",
        data={"term_type": "generic_keyword", "redirect": "/novelty/known-pending"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    response = client.post(
        f"/opportunities/{opp_id}/archive",
        data={"redirect": "/opportunities"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_known_pending_page_loads(novelty_db: Path) -> None:
    _, candidate_id, _ = _seed_opportunity(novelty_db)
    add_to_known_pending(
        novelty_db,
        "dog ACL surgery payment plan",
        "brand",
        "pet_financing",
        candidate_id,
    )
    client = TestClient(create_app(db_path=novelty_db))
    response = client.get("/novelty/known-pending")
    assert response.status_code == 200
    assert "dog ACL surgery payment plan" in response.text
