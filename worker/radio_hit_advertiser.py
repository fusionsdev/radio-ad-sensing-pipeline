"""Investigate radio-detected advertisers and seed trademark keyword candidates."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alerter.hit_advertiser import HitAdvertiserAlert, send_hit_advertiser_alert
from shared.db import get_connection, retry_on_busy, transaction
from worker.advertiser_intel import _extract_cta, _extract_domain, _extract_phone

SEARCH_TERMS = ("billshappen.com", "bills happen", "billshappen")

DEFAULT_TRADEMARK_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("billshappen", "brand"),
    ("billshappen.com", "brand"),
    ("bills happen", "brand"),
    ("bills happen loans", "product"),
    ("billshappen loans", "product"),
    ("billshappen personal loan", "product"),
    ("billshappen reviews", "reviews"),
    ("billshappen legit", "intent"),
    ("billshappen complaints", "complaints"),
    ("billshappen alternative", "alternative"),
    ("billshappen phone number", "contact"),
)

_CTA_FALLBACK_RE = re.compile(
    r"(if you need extra cash[^.!?]{0,120}|go to [^.!?]{0,80})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DetectionEvidence:
    detection_id: int
    station_id: int
    station_name: str
    station_display_name: str
    market: str | None
    timestamp: float
    transcript: str
    audio_clip_path: str | None
    audio_clip_start_sec: float | None
    audio_clip_end_sec: float | None
    website: str | None
    phone_number: str | None
    cta: str | None
    offer_summary: str | None
    key_claims: list[str]
    confidence: float | None
    chunk_id: int


@dataclass
class InvestigationResult:
    canonical_name: str
    normalized_name: str
    vertical: str
    domain: str | None
    source_type: str
    confidence: str
    status: str
    advertiser_entity_id: int
    trademark_entity_id: int
    detections: list[DetectionEvidence] = field(default_factory=list)
    trademark_keywords_created: int = 0
    trademark_keywords_existing: int = 0
    evidence_path: Path | None = None
    alert_sent: bool = False


def normalize_advertiser_name(name: str) -> str:
    cleaned = re.sub(r"https?://", "", name.lower())
    cleaned = cleaned.replace("www.", "")
    cleaned = re.sub(r"\.(com|net|org|io)$", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned.strip(".") or name.lower()


def parse_market(display_name: str | None) -> str | None:
    if not display_name:
        return None
    if "—" in display_name:
        parts = display_name.split("—", 1)
        if len(parts) == 2:
            return parts[1].strip() or None
    if " - " in display_name:
        parts = display_name.split(" - ", 1)
        if len(parts) == 2:
            return parts[1].strip() or None
    return None


def parse_key_claims(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _ad_segment_bounds(segments_json: str | None) -> tuple[float | None, float | None]:
    if not segments_json:
        return None, None
    try:
        segments = json.loads(segments_json)
    except json.JSONDecodeError:
        return None, None
    starts: list[float] = []
    ends: list[float] = []
    for segment in segments:
        text = str(segment.get("text", "")).lower()
        if any(term.replace(".", "") in text.replace(".", "") for term in SEARCH_TERMS):
            starts.append(float(segment["start"]))
            ends.append(float(segment["end"]))
    if not starts:
        return None, None
    start = max(0.0, min(starts) - 2.0)
    end = min(max(ends) + 2.0, start + 60.0)
    if end - start < 30.0:
        end = start + 30.0
    return round(start, 2), round(end, 2)


def _billshappen_excerpt(transcript: str) -> str:
    lowered = transcript.lower()
    for needle in ("billshappen.com", "bills happen", "billshappen"):
        idx = lowered.find(needle.replace(".", ""))
        if idx == -1:
            idx = lowered.find(needle)
        if idx != -1:
            start = max(0, idx - 120)
            end = min(len(transcript), idx + 280)
            return transcript[start:end]
    return transcript


def _extract_cta_from_transcript(transcript: str) -> str | None:
    excerpt = _billshappen_excerpt(transcript)
    cta = _extract_cta(excerpt)
    if cta:
        return cta.strip()
    match = _CTA_FALLBACK_RE.search(excerpt)
    if match:
        return match.group(1).strip()
    return None


def _search_clause(alias: str = "t") -> str:
    parts = [
        f"LOWER(COALESCE({alias}.text, '')) LIKE ?",
        f"LOWER(COALESCE({alias}.text, '')) LIKE ?",
        f"LOWER(COALESCE({alias}.text, '')) LIKE ?",
        "LOWER(COALESCE(d.website, '')) LIKE ?",
        "LOWER(COALESCE(d.company_name, '')) LIKE ?",
        "LOWER(COALESCE(d.offer_summary, '')) LIKE ?",
    ]
    return "(" + " OR ".join(parts) + ")"


def _search_params() -> tuple[str, ...]:
    return (
        "%billshappen%",
        "%bills happen%",
        "%billshappen.com%",
        "%billshappen%",
        "%billshappen%",
        "%billshappen%",
    )


@retry_on_busy()
def fetch_detection_evidence(
    conn: sqlite3.Connection,
    *,
    station_names: tuple[str, ...] | None = None,
) -> list[DetectionEvidence]:
    """Pull detections whose transcript or extraction references the search terms."""
    params: list[Any] = list(_search_params())
    station_clause = ""
    if station_names:
        placeholders = ", ".join("?" for _ in station_names)
        station_clause = f" AND s.name IN ({placeholders})"
        params.extend(station_names)

    rows = conn.execute(
        f"""
        SELECT d.id AS detection_id, d.company_name, d.website, d.phone_number,
               d.offer_summary, d.key_claims, d.confidence,
               c.id AS chunk_id, c.station_id, c.path, c.start_ts,
               s.name AS station_name, s.display_name,
               t.text AS transcript, t.segments_json
        FROM detections d
        JOIN chunks c ON c.id = d.chunk_id
        JOIN stations s ON s.id = c.station_id
        LEFT JOIN transcripts t ON t.chunk_id = c.id
        WHERE d.is_ad = 1 AND {_search_clause("t")} {station_clause}
        ORDER BY c.start_ts
        """,
        tuple(params),
    ).fetchall()

    evidence: list[DetectionEvidence] = []
    for row in rows:
        transcript = row["transcript"] or ""
        phone, _vanity = _extract_phone(transcript)
        website = row["website"] or _extract_domain(transcript)
        clip_start, clip_end = _ad_segment_bounds(row["segments_json"])
        display = row["display_name"] or row["station_name"]
        evidence.append(
            DetectionEvidence(
                detection_id=int(row["detection_id"]),
                station_id=int(row["station_id"]),
                station_name=str(row["station_name"]),
                station_display_name=str(display),
                market=parse_market(str(display) if display else None),
                timestamp=float(row["start_ts"]),
                transcript=transcript,
                audio_clip_path=row["path"],
                audio_clip_start_sec=clip_start,
                audio_clip_end_sec=clip_end,
                website=website,
                phone_number=row["phone_number"] or phone,
                cta=_extract_cta_from_transcript(transcript),
                offer_summary=row["offer_summary"],
                key_claims=parse_key_claims(row["key_claims"]),
                confidence=float(row["confidence"]) if row["confidence"] is not None else None,
                chunk_id=int(row["chunk_id"]),
            )
        )
    return evidence


def _ensure_trademark_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(trademark_keyword_candidates)").fetchall()
    }
    additions = {
        "verification_status": "TEXT NOT NULL DEFAULT 'needs_review'",
        "trademark_risk": "TEXT NOT NULL DEFAULT 'unknown'",
        "landing_page_allowed": "INTEGER NOT NULL DEFAULT 1",
    }
    for name, ddl in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE trademark_keyword_candidates ADD COLUMN {name} {ddl}")


def _upsert_trademark_entity(
    conn: sqlite3.Connection,
    *,
    canonical_name: str,
    normalized_name: str,
    source_type: str,
    review_status: str,
    now_iso: str,
) -> int:
    row = conn.execute(
        "SELECT id FROM trademark_entities WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    if row:
        entity_id = int(row["id"])
        conn.execute(
            """
            UPDATE trademark_entities
            SET canonical_name = ?, source_type = ?, review_status = ?,
                trademark_risk = 'unknown', ad_copy_allowed = 0,
                landing_page_allowed = 1, updated_at = ?
            WHERE id = ?
            """,
            (canonical_name, source_type, review_status, now_iso, entity_id),
        )
        return entity_id

    conn.execute(
        """
        INSERT INTO trademark_entities (
            canonical_name, normalized_name, source_type, review_status,
            trademark_risk, ad_copy_allowed, landing_page_allowed, reason,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'unknown', 0, 1, ?, ?, ?)
        """,
        (
            canonical_name,
            normalized_name,
            source_type,
            review_status,
            "Radio transcript evidence; manual review required before ad copy use.",
            now_iso,
            now_iso,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _ensure_trademark_alias(
    conn: sqlite3.Connection,
    *,
    entity_id: int,
    alias_name: str,
    source_type: str,
    now_iso: str,
) -> None:
    normalized = alias_name.lower().strip()
    exists = conn.execute(
        """
        SELECT 1 FROM trademark_aliases
        WHERE trademark_entity_id = ? AND normalized_alias = ?
        """,
        (entity_id, normalized),
    ).fetchone()
    if exists:
        return
    conn.execute(
        """
        INSERT INTO trademark_aliases (
            trademark_entity_id, alias_name, normalized_alias, source_type, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (entity_id, alias_name, normalized, source_type, now_iso),
    )


def _seed_trademark_keywords(
    conn: sqlite3.Connection,
    *,
    entity_id: int,
    source_type: str,
    keywords: tuple[tuple[str, str], ...],
    confidence: float,
) -> tuple[int, int]:
    created = 0
    existing = 0
    for keyword, variant_type in keywords:
        normalized = keyword.lower().strip()
        row = conn.execute(
            """
            SELECT id FROM trademark_keyword_candidates
            WHERE trademark_entity_id = ? AND normalized_keyword = ?
            """,
            (entity_id, normalized),
        ).fetchone()
        if row:
            existing += 1
            continue
        conn.execute(
            """
            INSERT INTO trademark_keyword_candidates (
                trademark_entity_id, keyword, normalized_keyword, variant_type,
                source_type, status, ad_copy_allowed, confidence, score,
                verification_status, trademark_risk, landing_page_allowed
            ) VALUES (?, ?, ?, ?, ?, 'new', 0, ?, ?, 'needs_review', 'unknown', 1)
            """,
            (entity_id, keyword, normalized, variant_type, source_type, confidence, confidence * 100),
        )
        created += 1
    return created, existing


def _upsert_advertiser_entity(
    conn: sqlite3.Connection,
    *,
    canonical_name: str,
    normalized_name: str,
    vertical: str,
    domain: str | None,
    source_type: str,
    confidence: str,
    status: str,
    trademark_entity_id: int,
    evidence_path: str | None,
    now_ts: float,
) -> int:
    row = conn.execute(
        "SELECT id FROM advertiser_entities WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    if row:
        entity_id = int(row["id"])
        conn.execute(
            """
            UPDATE advertiser_entities
            SET canonical_name = ?, vertical = ?, domain = ?, source_type = ?,
                confidence = ?, status = ?, trademark_entity_id = ?,
                evidence_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                canonical_name,
                vertical,
                domain,
                source_type,
                confidence,
                status,
                trademark_entity_id,
                evidence_path,
                now_ts,
                entity_id,
            ),
        )
        return entity_id

    conn.execute(
        """
        INSERT INTO advertiser_entities (
            canonical_name, normalized_name, vertical, domain, source_type,
            confidence, status, trademark_entity_id, evidence_path,
            hit_advertiser_alerted, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            canonical_name,
            normalized_name,
            vertical,
            domain,
            source_type,
            confidence,
            status,
            trademark_entity_id,
            evidence_path,
            now_ts,
            now_ts,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _link_detection(
    conn: sqlite3.Connection,
    *,
    advertiser_entity_id: int,
    detection: DetectionEvidence,
    now_ts: float,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO advertiser_entity_detections (
            advertiser_entity_id, detection_id, chunk_id, station_id,
            station_display_name, market, hit_ts, audio_clip_path,
            audio_clip_start_sec, audio_clip_end_sec, transcript, website,
            phone_number, cta, offer_summary, key_claims, detection_confidence,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            advertiser_entity_id,
            detection.detection_id,
            detection.chunk_id,
            detection.station_id,
            detection.station_display_name,
            detection.market,
            detection.timestamp,
            detection.audio_clip_path,
            detection.audio_clip_start_sec,
            detection.audio_clip_end_sec,
            detection.transcript,
            detection.website,
            detection.phone_number,
            detection.cta,
            detection.offer_summary,
            json.dumps(detection.key_claims),
            detection.confidence,
            now_ts,
        ),
    )


def render_evidence_markdown(
    result: InvestigationResult,
    *,
    generated_at: datetime | None = None,
) -> str:
    ts = generated_at or datetime.now(tz=UTC)
    lines = [
        f"# Billshappen.com — Radio Detection Evidence Pack",
        "",
        f"Generated: {ts.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Advertiser summary",
        "",
        f"| Field | Value |",
        f"| --- | --- |",
        f"| Canonical name | {result.canonical_name} |",
        f"| Normalized name | `{result.normalized_name}` |",
        f"| Vertical | `{result.vertical}` |",
        f"| Domain | `{result.domain or '—'}` |",
        f"| Source type | `{result.source_type}` |",
        f"| Confidence | {result.confidence} |",
        f"| Status | `{result.status}` |",
        f"| Advertiser entity ID | {result.advertiser_entity_id} |",
        f"| Trademark entity ID | {result.trademark_entity_id} |",
        f"| Linked detections | {len(result.detections)} |",
        f"| Trademark keywords created | {result.trademark_keywords_created} |",
        "",
        "## Detection evidence",
        "",
    ]
    for idx, det in enumerate(result.detections, start=1):
        ts_label = datetime.fromtimestamp(det.timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        clip = "—"
        if det.audio_clip_start_sec is not None and det.audio_clip_end_sec is not None:
            clip = f"{det.audio_clip_start_sec:.1f}s–{det.audio_clip_end_sec:.1f}s of chunk"
        lines.extend(
            [
                f"### {idx}. {det.station_display_name}",
                "",
                f"- **Detection ID:** {det.detection_id}",
                f"- **Station ID:** {det.station_id} (`{det.station_name}`)",
                f"- **Market:** {det.market or '—'}",
                f"- **Timestamp:** {ts_label}",
                f"- **Website:** {det.website or '—'}",
                f"- **Phone:** {det.phone_number or '—'}",
                f"- **CTA:** {det.cta or '—'}",
                f"- **Offer summary:** {det.offer_summary or '—'}",
                f"- **Key claims:** {', '.join(det.key_claims) if det.key_claims else '—'}",
                f"- **Confidence:** {det.confidence if det.confidence is not None else '—'}",
                f"- **Audio clip path:** `{det.audio_clip_path or '—'}`",
                f"- **Suggested clip window:** {clip}",
                "",
                "**Transcript**",
                "",
                "```",
                det.transcript.strip(),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Trademark keyword candidates",
            "",
            "All candidates remain `status=new`, `verification_status=needs_review`, "
            "`ad_copy_allowed=false`, `landing_page_allowed=true`, `trademark_risk=unknown`.",
            "Do not auto-export to Google Ads.",
            "",
            "| Keyword | Variant |",
            "| --- | --- |",
        ]
    )
    for keyword, variant in DEFAULT_TRADEMARK_KEYWORDS:
        lines.append(f"| `{keyword}` | {variant} |")
    lines.extend(
        [
            "",
            "## Review links",
            "",
            "- Dashboard: `/advertisers/opportunities`",
            "- Trademark keywords: `/keywords/trademark`",
            "",
        ]
    )
    return "\n".join(lines)


@retry_on_busy()
def investigate_radio_advertiser(
    db_path: str | Path,
    *,
    canonical_name: str,
    normalized_name: str,
    vertical: str,
    domain: str | None,
    source_type: str = "radio_transcript",
    confidence: str = "high",
    status: str = "needs_review",
    station_names: tuple[str, ...] | None = None,
    trademark_keywords: tuple[tuple[str, str], ...] = DEFAULT_TRADEMARK_KEYWORDS,
    evidence_path: Path | None = None,
    send_alert: bool = True,
    dry_run: bool = False,
) -> InvestigationResult:
    """Create/update advertiser + trademark records from live radio detections."""
    detections = []
    conn = get_connection(db_path)
    try:
        detections = fetch_detection_evidence(conn, station_names=station_names)
    finally:
        conn.close()

    if not detections:
        raise ValueError(f"No detections found for search terms: {SEARCH_TERMS}")

    resolved_domain = domain or next((d.website for d in detections if d.website), None)
    now_ts = time.time()
    now_iso = datetime.fromtimestamp(now_ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    avg_conf = next((d.confidence for d in detections if d.confidence is not None), 0.9)

    if dry_run:
        return InvestigationResult(
            canonical_name=canonical_name,
            normalized_name=normalized_name,
            vertical=vertical,
            domain=resolved_domain,
            source_type=source_type,
            confidence=confidence,
            status=status,
            advertiser_entity_id=0,
            trademark_entity_id=0,
            detections=detections,
        )

    conn = get_connection(db_path)
    alert_sent = False
    try:
        with transaction(conn):
            _ensure_trademark_columns(conn)
            trademark_entity_id = _upsert_trademark_entity(
                conn,
                canonical_name=canonical_name,
                normalized_name=normalized_name,
                source_type=source_type,
                review_status=status,
                now_iso=now_iso,
            )
            for alias in {canonical_name, "Bills Happen", "BillsHappen.com"}:
                _ensure_trademark_alias(
                    conn,
                    entity_id=trademark_entity_id,
                    alias_name=alias,
                    source_type=source_type,
                    now_iso=now_iso,
                )
            kw_created, kw_existing = _seed_trademark_keywords(
                conn,
                entity_id=trademark_entity_id,
                source_type=source_type,
                keywords=trademark_keywords,
                confidence=float(avg_conf),
            )
            advertiser_entity_id = _upsert_advertiser_entity(
                conn,
                canonical_name=canonical_name,
                normalized_name=normalized_name,
                vertical=vertical,
                domain=resolved_domain,
                source_type=source_type,
                confidence=confidence,
                status=status,
                trademark_entity_id=trademark_entity_id,
                evidence_path=str(evidence_path) if evidence_path else None,
                now_ts=now_ts,
            )
            for detection in detections:
                _link_detection(
                    conn,
                    advertiser_entity_id=advertiser_entity_id,
                    detection=detection,
                    now_ts=now_ts,
                )

        result = InvestigationResult(
            canonical_name=canonical_name,
            normalized_name=normalized_name,
            vertical=vertical,
            domain=resolved_domain,
            source_type=source_type,
            confidence=confidence,
            status=status,
            advertiser_entity_id=advertiser_entity_id,
            trademark_entity_id=trademark_entity_id,
            detections=detections,
            trademark_keywords_created=kw_created,
            trademark_keywords_existing=kw_existing,
            evidence_path=evidence_path,
        )

        if evidence_path is not None:
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(render_evidence_markdown(result), encoding="utf-8")
            with transaction(conn):
                conn.execute(
                    "UPDATE advertiser_entities SET evidence_path = ?, updated_at = ? WHERE id = ?",
                    (str(evidence_path), time.time(), advertiser_entity_id),
                )

        if send_alert:
            alert = HitAdvertiserAlert(
                advertiser_entity_id=advertiser_entity_id,
                canonical_name=canonical_name,
                normalized_name=normalized_name,
                vertical=vertical,
                domain=resolved_domain,
                confidence=confidence,
                detection_count=len(detections),
                stations=tuple(sorted({d.station_display_name for d in detections})),
                markets=tuple(sorted({d.market for d in detections if d.market})),
                evidence_path=str(evidence_path) if evidence_path else None,
                sample_offer=detections[0].offer_summary,
            )
            alert_sent = send_hit_advertiser_alert(conn, alert)
        result.alert_sent = alert_sent
        return result
    finally:
        conn.close()
