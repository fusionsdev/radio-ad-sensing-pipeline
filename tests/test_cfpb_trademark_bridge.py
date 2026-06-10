"""Tests for CFPB trademark bridge."""

from __future__ import annotations

from pathlib import Path

from collectors.bridges.trademark_bridge import table_exists, upsert_trademark_from_entity
from shared.db import get_connection, migrate
from shared.models import TrademarkLayerSettings


def test_bridge_creates_trademark_entity(tmp_path: Path) -> None:
    db_path = tmp_path / "bridge.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO cfpb_company_entities (
                company_raw, company_normalized, trademark_candidate_score, review_status
            ) VALUES ('CashNetUSA', 'cashnetusa', 85, 'new')
            """
        )
        conn.commit()
        entity_id = int(cursor.lastrowid)
        tm_id = upsert_trademark_from_entity(
            conn,
            entity_id=entity_id,
            company_raw="CashNetUSA",
            company_normalized="cashnetusa",
            trademark_score=85.0,
            settings=TrademarkLayerSettings(min_bridge_score=70),
        )
        conn.commit()
        assert tm_id is not None
        row = conn.execute(
            "SELECT source_type, review_status, ad_copy_allowed FROM trademark_entities WHERE id = ?",
            (tm_id,),
        ).fetchone()
        assert row["source_type"] == "cfpb_complaint"
        assert row["review_status"] == "new"
        assert row["ad_copy_allowed"] == 0
        keywords = conn.execute(
            "SELECT status, ad_copy_allowed FROM trademark_keyword_candidates WHERE trademark_entity_id = ?",
            (tm_id,),
        ).fetchall()
        assert len(keywords) >= 6
        assert all(r["status"] == "new" for r in keywords)
        assert all(r["ad_copy_allowed"] == 0 for r in keywords)
    finally:
        conn.close()


def test_bridge_auto_approves_when_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "auto.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO cfpb_company_entities (
                company_raw, company_normalized, trademark_candidate_score, review_status
            ) VALUES ('Strong Co', 'strong co', 90, 'new')
            """
        )
        conn.commit()
        entity_id = int(cursor.lastrowid)
        tm_id = upsert_trademark_from_entity(
            conn,
            entity_id=entity_id,
            company_raw="Strong Co",
            company_normalized="strong co",
            trademark_score=90.0,
            settings=TrademarkLayerSettings(min_bridge_score=70, auto_approve_enabled=True),
            auto_approve=True,
            auto_approve_min_score=85.0,
        )
        conn.commit()
        assert tm_id is not None
        row = conn.execute(
            "SELECT review_status, ad_copy_allowed FROM trademark_entities WHERE id = ?",
            (tm_id,),
        ).fetchone()
        assert row["review_status"] == "approved_seed"
        assert row["ad_copy_allowed"] == 0
        kw = conn.execute(
            "SELECT status FROM trademark_keyword_candidates WHERE trademark_entity_id = ? LIMIT 1",
            (tm_id,),
        ).fetchone()
        assert kw["status"] == "approved_seed"
    finally:
        conn.close()


def test_bridge_skips_below_threshold(tmp_path: Path) -> None:
    db_path = tmp_path / "skip.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        result = upsert_trademark_from_entity(
            conn,
            entity_id=1,
            company_raw="Weak Co",
            company_normalized="weak co",
            trademark_score=40.0,
            settings=TrademarkLayerSettings(min_bridge_score=70),
        )
        assert result is None
    finally:
        conn.close()


def test_table_exists_helper(tmp_path: Path) -> None:
    db_path = tmp_path / "tables.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        assert table_exists(conn, "trademark_entities")
        assert not table_exists(conn, "nonexistent_table")
    finally:
        conn.close()
