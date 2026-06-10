"""Bridge strong CFPB entities into the trademark keyword research layer."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from shared.models import TrademarkLayerSettings

from collectors.auto_approve import review_status_for_score

CFPB_SOURCE = "cfpb_complaint"
CFPB_REASON = (
    "Derived from CFPB complaint company/entity data; requires verification."
)

DEFAULT_VARIANTS = ("reviews", "complaints", "bbb", "phone number", "alternative")


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def upsert_trademark_from_entity(
    conn: sqlite3.Connection,
    *,
    entity_id: int,
    company_raw: str,
    company_normalized: str,
    trademark_score: float,
    settings: TrademarkLayerSettings,
    auto_approve: bool = False,
    auto_approve_min_score: float = 85.0,
) -> int | None:
    """Upsert trademark_entities and conservative keyword variants."""
    if not table_exists(conn, "trademark_entities"):
        return None
    if trademark_score < settings.min_bridge_score:
        return None

    approve = auto_approve or settings.auto_approve_enabled
    min_approve = (
        auto_approve_min_score
        if auto_approve
        else settings.auto_approve_min_score
    )
    entity_review = review_status_for_score(
        trademark_score, enabled=approve, min_score=min_approve
    )
    keyword_status = "approved_seed" if entity_review == "approved_seed" else "new"

    existing = conn.execute(
        "SELECT id FROM trademark_entities WHERE normalized_name = ?",
        (company_normalized,),
    ).fetchone()
    now = _now_iso()
    if existing:
        trademark_id = int(existing[0])
        conn.execute(
            """
            UPDATE trademark_entities
            SET updated_at = ?, cfpb_company_entity_id = ?, reason = ?,
                review_status = CASE
                    WHEN ? = 'approved_seed' THEN 'approved_seed'
                    ELSE review_status
                END
            WHERE id = ?
            """,
            (now, entity_id, CFPB_REASON, entity_review, trademark_id),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO trademark_entities (
                canonical_name, normalized_name, source_type, review_status,
                trademark_risk, ad_copy_allowed, landing_page_allowed,
                reason, cfpb_company_entity_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'unknown', 0, 1, ?, ?, ?, ?)
            """,
            (
                company_raw,
                company_normalized,
                CFPB_SOURCE,
                entity_review,
                CFPB_REASON,
                entity_id,
                now,
                now,
            ),
        )
        trademark_id = int(cursor.lastrowid)

    conn.execute(
        """
        UPDATE cfpb_company_entities
        SET trademark_entity_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (trademark_id, now, entity_id),
    )

    _ensure_alias(conn, trademark_id, company_raw, company_normalized)
    _ensure_keyword_variants(
        conn,
        trademark_id,
        company_normalized,
        trademark_score,
        settings.conservative_variants or list(DEFAULT_VARIANTS),
        keyword_status=keyword_status,
    )
    return trademark_id


def _ensure_alias(
    conn: sqlite3.Connection,
    trademark_id: int,
    alias_name: str,
    normalized_alias: str,
) -> None:
    if not table_exists(conn, "trademark_aliases"):
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO trademark_aliases (
            trademark_entity_id, alias_name, normalized_alias, source_type, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (trademark_id, alias_name, normalized_alias, CFPB_SOURCE, _now_iso()),
    )


def _ensure_keyword_variants(
    conn: sqlite3.Connection,
    trademark_id: int,
    brand: str,
    score: float,
    variants: list[str],
    *,
    keyword_status: str = "new",
) -> None:
    if not table_exists(conn, "trademark_keyword_candidates"):
        return
    now = _now_iso()
    base_keyword = brand.strip()
    rows = [(base_keyword, base_keyword, "brand")]
    for variant in variants:
        keyword = f"{base_keyword} {variant}".strip()
        rows.append((keyword, keyword.lower(), variant.replace(" ", "_")))
    for keyword, normalized, variant_type in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO trademark_keyword_candidates (
                trademark_entity_id, keyword, normalized_keyword, variant_type,
                source_type, status, ad_copy_allowed, confidence, score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                trademark_id,
                keyword,
                normalized,
                variant_type,
                CFPB_SOURCE,
                keyword_status,
                min(score / 100.0, 1.0),
                score,
                now,
            ),
        )
