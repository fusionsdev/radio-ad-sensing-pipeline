"""Extract advertiser intelligence from keyword-hit transcript windows."""

from __future__ import annotations

import re
import sqlite3
import time

from shared.verticals import source_keywords_json
from worker.extract import normalize_phone_number

_DOMAIN_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?"
    r"([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?:1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}"
    r"|\b1[-.\s]?8(?:00|88|77|66|55|44|33)[-.\s]?\d{3}[-.\s]?\d{4}\b",
    re.IGNORECASE,
)
_VANITY_RE = re.compile(
    r"\b1[-.\s]?8(?:00|88|77|66|55|44|33)[-.\s]?[A-Z0-9-]{7,}\b",
    re.IGNORECASE,
)
_CTA_RE = re.compile(
    r"\b(call(?:\s+us)?(?:\s+now)?|visit(?:\s+us)?(?:\s+online)?|"
    r"go to|text|apply(?:\s+now)?|schedule(?:\s+a)?(?:\s+free)?(?:\s+consultation)?)\b[^.!?]{0,80}",
    re.IGNORECASE,
)
_COMPANY_SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&'.\- ]{2,40}(?:LLC|Inc|Corp|Company|Center|Group|Services|Solutions))\b"
)


def _extract_domain(text: str) -> str | None:
    match = _DOMAIN_RE.search(text)
    if match is None:
        return None
    return match.group(1).lower()


def _extract_phone(text: str) -> tuple[str | None, str | None]:
    vanity_match = _VANITY_RE.search(text)
    if vanity_match:
        raw = vanity_match.group(0)
        normalized = normalize_phone_number(raw)
        return normalized, raw.strip()
    phone_match = _PHONE_RE.search(text)
    if phone_match:
        raw = phone_match.group(0)
        return normalize_phone_number(raw), None
    return None, None


def _extract_company(text: str) -> str | None:
    match = _COMPANY_SUFFIX_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def _extract_cta(text: str) -> str | None:
    match = _CTA_RE.search(text)
    if match:
        return match.group(0).strip()
    return None


def _offer_from_keywords(keywords: list[str]) -> str | None:
    if not keywords:
        return None
    return f"Radio mention: {', '.join(sorted(keywords))}"


def extract_advertiser_intel(
    *,
    transcript: str,
    source_keywords: list[str],
    detection_row: sqlite3.Row | dict | None = None,
) -> dict[str, str | float | None]:
    """Regex + detection merge for advertiser opportunity fields."""
    text = transcript or ""
    det = dict(detection_row) if detection_row is not None else {}

    phone, vanity = _extract_phone(text)
    domain = _extract_domain(text)
    company = _extract_company(text) or det.get("company_name")
    offer = det.get("offer_summary") or _offer_from_keywords(source_keywords)
    cta = _extract_cta(text)

    if det.get("phone_number"):
        phone = normalize_phone_number(str(det["phone_number"])) or phone
    if det.get("website"):
        domain = _extract_domain(str(det["website"])) or domain

    confidence = float(det["confidence"]) if det.get("confidence") is not None else 0.55

    return {
        "company_name": company,
        "domain": domain,
        "phone_number": phone,
        "vanity_phone": vanity,
        "offer_summary": offer,
        "cta": cta,
        "confidence": confidence,
    }


def record_advertiser_opportunity(
    conn: sqlite3.Connection,
    *,
    vertical: str,
    station_id: int,
    chunk_id: int,
    keyword_hit_id: int | None,
    hit_ts: float,
    source_keywords: list[str],
    audio_clip_path: str | None,
    intel: dict[str, str | float | None],
) -> int:
    """Insert advertiser opportunity; never auto-approves (approved stays 0)."""
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO advertiser_opportunities (
            vertical, station_id, chunk_id, keyword_hit_id,
            company_name, domain, phone_number, vanity_phone,
            offer_summary, cta, hit_ts, audio_clip_path,
            source_keywords, confidence, approved, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            vertical,
            station_id,
            chunk_id,
            keyword_hit_id,
            intel.get("company_name"),
            intel.get("domain"),
            intel.get("phone_number"),
            intel.get("vanity_phone"),
            intel.get("offer_summary"),
            intel.get("cta"),
            hit_ts,
            audio_clip_path,
            source_keywords_json(source_keywords),
            intel.get("confidence"),
            time.time(),
        ),
    )
    return cursor.rowcount
