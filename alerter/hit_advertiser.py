"""One-shot HIT_ADVERTISER Telegram alert for radio-detected advertisers."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

import httpx

from shared.config import load_telegram_settings
from shared.db import transaction

STATUS_KEY_PREFIX = "alerter:hit_advertiser:"


@dataclass(frozen=True)
class HitAdvertiserAlert:
    advertiser_entity_id: int
    canonical_name: str
    normalized_name: str
    vertical: str
    domain: str | None
    confidence: str
    detection_count: int
    stations: tuple[str, ...]
    markets: tuple[str, ...]
    evidence_path: str | None
    sample_offer: str | None


def _status_key(normalized_name: str) -> str:
    return f"{STATUS_KEY_PREFIX}{normalized_name}"


def already_alerted(conn: sqlite3.Connection, normalized_name: str) -> bool:
    row = conn.execute(
        "SELECT value FROM status WHERE key = ?",
        (_status_key(normalized_name),),
    ).fetchone()
    return row is not None


def format_hit_advertiser_message(alert: HitAdvertiserAlert) -> str:
    lines = [
        "HIT_ADVERTISER — radio-detected personal-loan advertiser",
        f"Advertiser: {alert.canonical_name}",
        f"Domain: {alert.domain or 'unknown'}",
        f"Vertical: {alert.vertical}",
        f"Confidence: {alert.confidence}",
        f"Detections: {alert.detection_count} across {len(alert.stations)} station(s)",
        f"Stations: {', '.join(alert.stations)}",
    ]
    if alert.markets:
        lines.append(f"Markets: {', '.join(alert.markets)}")
    if alert.sample_offer:
        lines.append(f"Offer: {alert.sample_offer}")
    if alert.evidence_path:
        lines.append(f"Evidence: {alert.evidence_path}")
    lines.append("Review: /advertisers/opportunities · trademark keywords pending approval")
    return "\n".join(lines)


def _send_telegram_message(token: str, chat_id: str, text: str) -> None:
    with httpx.Client(
        base_url=f"https://api.telegram.org/bot{token}",
        timeout=10.0,
    ) as client:
        response = client.post(
            "sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok", False):
            raise RuntimeError(f"Telegram sendMessage failed: {payload!r}")


def send_hit_advertiser_alert(
    conn: sqlite3.Connection,
    alert: HitAdvertiserAlert,
    *,
    dry_run: bool = False,
    clock: Any | None = None,
) -> bool:
    """Send HIT_ADVERTISER Telegram alert once per normalized advertiser name."""
    if already_alerted(conn, alert.normalized_name):
        return False

    message = format_hit_advertiser_message(alert)
    settings = load_telegram_settings()
    now_ts = time.time() if clock is None else float(clock())
    has_telegram = bool(settings.telegram_bot_token and settings.telegram_chat_id)

    if dry_run or not has_telegram:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO status (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (_status_key(alert.normalized_name), "dry_run", now_ts),
            )
            conn.execute(
                """
                UPDATE advertiser_entities
                SET hit_advertiser_alerted = 1, updated_at = ?
                WHERE id = ?
                """,
                (now_ts, alert.advertiser_entity_id),
            )
        return True

    _send_telegram_message(
        settings.telegram_bot_token or "",
        settings.telegram_chat_id or "",
        message,
    )

    with transaction(conn):
        conn.execute(
            """
            INSERT INTO status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (_status_key(alert.normalized_name), "sent", now_ts),
        )
        conn.execute(
            """
            UPDATE advertiser_entities
            SET hit_advertiser_alerted = 1, updated_at = ?
            WHERE id = ?
            """,
            (now_ts, alert.advertiser_entity_id),
        )
    return True
