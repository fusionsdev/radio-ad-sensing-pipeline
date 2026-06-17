"""Telegram / dry-run reporter for novelty keyword opportunities."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

from shared.config import CONFIG_DIR
from shared.db import get_connection

DEFAULT_RULES_PATH = CONFIG_DIR / "novelty_rules.yaml"


@dataclass(frozen=True)
class NoveltyOpportunityAlert:
    id: int
    opportunity_text: str
    opportunity_type: str
    vertical: str | None
    source_type: str
    source_url: str | None
    evidence_text: str | None
    novelty_score: float
    opportunity_score: float
    suggested_action: str | None


def load_report_thresholds(rules_path: Path | None = None) -> tuple[float, float]:
    path = rules_path or DEFAULT_RULES_PATH
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    thresholds = data.get("thresholds", {})
    return (
        float(thresholds.get("report_novelty_score", 75)),
        float(thresholds.get("report_opportunity_score", 70)),
    )


def fetch_pending_opportunities(
    db_path: str | Path,
    *,
    rules_path: Path | None = None,
    limit: int = 20,
    include_approved: bool = False,
) -> list[NoveltyOpportunityAlert]:
    """Return keyword_opportunities eligible for outbound reporting."""
    novelty_min, opportunity_min = load_report_thresholds(rules_path)
    allowed_statuses = ("new", "approved") if include_approved else ("new",)
    placeholders = ", ".join("?" for _ in allowed_statuses)
    conn = get_connection(db_path, read_only=True)
    try:
        rows = conn.execute(
            f"""
            SELECT
                ko.id, ko.opportunity_text, ko.opportunity_type, ko.vertical, ko.source_type,
                ko.source_url, ko.evidence_text, ko.novelty_score, ko.opportunity_score,
                ko.suggested_action
            FROM keyword_opportunities ko
            JOIN novelty_results nr ON nr.candidate_id = ko.candidate_id
            WHERE ko.status IN ({placeholders})
              AND ko.status NOT IN ('rejected', 'archived', 'noise')
              AND nr.reviewed_status NOT IN ('rejected', 'noise', 'archived')
              AND nr.novelty_status NOT IN ('noise')
              AND ko.novelty_score >= ?
              AND ko.opportunity_score >= ?
            ORDER BY ko.opportunity_score DESC, ko.created_at DESC
            LIMIT ?
            """,
            (*allowed_statuses, novelty_min, opportunity_min, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    return [
        NoveltyOpportunityAlert(
            id=int(row["id"]),
            opportunity_text=str(row["opportunity_text"]),
            opportunity_type=str(row["opportunity_type"]),
            vertical=row["vertical"],
            source_type=str(row["source_type"]),
            source_url=row["source_url"],
            evidence_text=row["evidence_text"],
            novelty_score=float(row["novelty_score"]),
            opportunity_score=float(row["opportunity_score"]),
            suggested_action=row["suggested_action"],
        )
        for row in rows
    ]


def format_opportunity_message(alert: NoveltyOpportunityAlert) -> str:
    """Dry-run Telegram formatter — safe to call without sending."""
    lines = [
        "🔍 Novel keyword opportunity",
        f"Phrase: {alert.opportunity_text}",
        f"Type: {alert.opportunity_type}",
    ]
    if alert.vertical:
        lines.append(f"Vertical: {alert.vertical}")
    lines.append(f"Novelty: {alert.novelty_score:.0f} | Score: {alert.opportunity_score:.0f}")
    if alert.suggested_action:
        lines.append(f"Action: {alert.suggested_action}")
    if alert.evidence_text:
        excerpt = alert.evidence_text.strip()
        if len(excerpt) > 240:
            excerpt = excerpt[:237] + "..."
        lines.append(f"Evidence: {excerpt}")
    if alert.source_url:
        lines.append(f"Source: {alert.source_url}")
    else:
        lines.append(f"Source type: {alert.source_type}")
    return "\n".join(lines)


def format_pending_digest(
    db_path: str | Path,
    *,
    rules_path: Path | None = None,
    limit: int = 10,
    include_approved: bool = False,
) -> str:
    """Build a multi-opportunity dry-run digest (does not send Telegram)."""
    alerts = fetch_pending_opportunities(
        db_path,
        rules_path=rules_path,
        limit=limit,
        include_approved=include_approved,
    )
    if not alerts:
        return "No novel keyword opportunities pending."
    parts = [format_opportunity_message(alert) for alert in alerts]
    return "\n\n---\n\n".join(parts)
