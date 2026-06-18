"""Tests for radio hit advertiser investigation."""

from __future__ import annotations

import json
from pathlib import Path

from shared.db import get_connection, migrate, transaction
from worker.radio_hit_advertiser import (
    DEFAULT_TRADEMARK_KEYWORDS,
    fetch_detection_evidence,
    investigate_radio_advertiser,
    normalize_advertiser_name,
    parse_market,
)


def _seed_billshappen_detection(conn, *, station: str, display: str, detection_id: int) -> None:
    conn.execute(
        "INSERT INTO stations (name, url, display_name, enabled) VALUES (?, ?, ?, 1)",
        (station, f"http://{station}", display),
    )
    station_id = conn.execute("SELECT id FROM stations WHERE name = ?", (station,)).fetchone()[0]
    conn.execute(
        """
        INSERT INTO chunks (station_id, path, start_ts, end_ts, status)
        VALUES (?, ?, ?, ?, 'done')
        """,
        (station_id, f"/tmp/{station}.wav", 100.0 + detection_id, 190.0 + detection_id),
    )
    chunk_id = conn.execute("SELECT MAX(id) FROM chunks").fetchone()[0]
    transcript = (
        "If you need extra cash, go to BillsHappen.com. "
        "BillsHappen.com is one of the largest personal loan networks."
    )
    conn.execute(
        "INSERT INTO transcripts (chunk_id, text) VALUES (?, ?)",
        (chunk_id, transcript),
    )
    conn.execute(
        """
        INSERT INTO detections (
            chunk_id, is_ad, company_name, website, offer_summary, key_claims, confidence, alerted
        ) VALUES (?, 1, ?, ?, ?, ?, ?, 0)
        """,
        (
            chunk_id,
            "Billshappen.com",
            "billshappen.com",
            "personal loans up to $5,000",
            json.dumps(["next-day funding"]),
            0.92,
        ),
    )


def test_normalize_and_market_helpers() -> None:
    assert normalize_advertiser_name("BillsHappen.com") == "billshappen"
    assert parse_market("KLIF 570 AM — Dallas, TX") == "Dallas, TX"


def test_investigate_radio_advertiser_creates_review_records(tmp_path: Path) -> None:
    db_path = tmp_path / "hit.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            for idx, (station, display) in enumerate(
                [
                    ("klif-am-570", "KLIF 570 AM — Dallas, TX"),
                    ("wsb-am-750", "WSB 750 AM — Atlanta, GA"),
                ]
            ):
                _seed_billshappen_detection(conn, station=station, display=display, detection_id=idx)
    finally:
        conn.close()

    evidence_path = tmp_path / "evidence.md"
    result = investigate_radio_advertiser(
        db_path,
        canonical_name="Billshappen.com",
        normalized_name="billshappen",
        vertical="personal_loan",
        domain="billshappen.com",
        trademark_keywords=DEFAULT_TRADEMARK_KEYWORDS,
        evidence_path=evidence_path,
        send_alert=False,
    )
    assert result.advertiser_entity_id > 0
    assert result.trademark_entity_id > 0
    assert len(result.detections) == 2
    assert result.trademark_keywords_created == len(DEFAULT_TRADEMARK_KEYWORDS)
    assert evidence_path.is_file()

    conn = get_connection(db_path)
    try:
        approved = conn.execute(
            "SELECT COUNT(*) FROM trademark_keyword_candidates WHERE status != 'new'"
        ).fetchone()[0]
        assert approved == 0
        ad_copy = conn.execute(
            "SELECT COUNT(*) FROM trademark_keyword_candidates WHERE ad_copy_allowed = 1"
        ).fetchone()[0]
        assert ad_copy == 0
        linked = conn.execute(
            "SELECT COUNT(*) FROM advertiser_entity_detections WHERE advertiser_entity_id = ?",
            (result.advertiser_entity_id,),
        ).fetchone()[0]
        assert linked == 2
    finally:
        conn.close()


def test_fetch_detection_evidence_filters_station(tmp_path: Path) -> None:
    db_path = tmp_path / "filter.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            _seed_billshappen_detection(
                conn, station="klif-am-570", display="KLIF", detection_id=1
            )
            _seed_billshappen_detection(
                conn, station="wibc-fm-931", display="WIBC", detection_id=2
            )
        rows = fetch_detection_evidence(
            conn, station_names=("klif-am-570", "wsb-am-750", "ktrh-am-740", "woai-am-1200")
        )
        assert len(rows) == 1
        assert rows[0].station_name == "klif-am-570"
    finally:
        conn.close()


def _seed_brand_detection(
    conn, *, station: str, display: str, brand: str, domain: str, detection_id: int
) -> None:
    conn.execute(
        "INSERT INTO stations (name, url, display_name, enabled) VALUES (?, ?, ?, 1)",
        (station, f"http://{station}", display),
    )
    station_id = conn.execute("SELECT id FROM stations WHERE name = ?", (station,)).fetchone()[0]
    conn.execute(
        "INSERT INTO chunks (station_id, path, start_ts, end_ts, status) VALUES (?, ?, ?, ?, 'done')",
        (station_id, f"/tmp/{station}.wav", 100.0 + detection_id, 190.0 + detection_id),
    )
    chunk_id = conn.execute("SELECT MAX(id) FROM chunks").fetchone()[0]
    transcript = f"Need a loan today? Go to {domain}. {brand} is a top personal loan network."
    conn.execute("INSERT INTO transcripts (chunk_id, text) VALUES (?, ?)", (chunk_id, transcript))
    conn.execute(
        """
        INSERT INTO detections (
            chunk_id, is_ad, company_name, website, offer_summary, key_claims, confidence, alerted
        ) VALUES (?, 1, ?, ?, ?, ?, ?, 0)
        """,
        (chunk_id, brand, domain, "personal loans", json.dumps(["fast funding"]), 0.9),
    )


def test_investigate_generalizes_to_any_brand(tmp_path: Path) -> None:
    # No hard-coded billshappen: a different brand is discovered, keyword variants
    # are derived from its name, and the evidence pack is titled for that brand.
    db_path = tmp_path / "brand.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            _seed_brand_detection(
                conn,
                station="kabc-am-790",
                display="KABC 790 AM — Los Angeles, CA",
                brand="LendingTree",
                domain="lendingtree.com",
                detection_id=1,
            )
    finally:
        conn.close()

    evidence_path = tmp_path / "lendingtree.md"
    result = investigate_radio_advertiser(
        db_path,
        canonical_name="LendingTree",
        normalized_name="lendingtree",
        vertical="personal_loan",
        domain="lendingtree.com",
        evidence_path=evidence_path,
        send_alert=False,
    )

    assert result.advertiser_entity_id > 0
    assert len(result.detections) == 1
    assert result.trademark_keywords_created == len(result.trademark_keywords)
    assert ("lendingtree", "brand") in result.trademark_keywords
    text = evidence_path.read_text(encoding="utf-8")
    assert "LendingTree — Radio Detection Evidence Pack" in text
    assert "billshappen" not in text.lower()
