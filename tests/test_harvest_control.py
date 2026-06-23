"""Tests for scripts/harvest_control.py (Safe Run Mode keyword harvest CLI)."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import pytest
import yaml

from scripts import harvest_control as hc
from shared.db import get_connection, migrate

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def profile() -> dict:
    return hc.load_profile("overnight_keyword_harvest")


@pytest.fixture
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect runtime + exports dirs into tmp_path so tests stay hermetic."""
    runtime = tmp_path / "runtime"
    exports = tmp_path / "exports"
    status_file = runtime / "harvest_status.json"
    monkeypatch.setattr(hc, "STATUS_FILE", status_file)
    monkeypatch.setattr(hc, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(hc, "EXPORTS_DIR", exports)
    return tmp_path


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Build a real schema via migrations and seed minimal harvest data."""
    db_path = tmp_path / "pipeline.db"
    migrate(db_path)
    conn = get_connection(db_path)
    try:
        # one station + chunk
        conn.execute("INSERT INTO stations(name, url, format, enabled, display_name) VALUES(?,?,?,?,?)",
                     ("wbap-am-820", "http://example/wbap", "mp3", 1, "WBAP"))
        conn.execute("INSERT INTO chunks(station_id, path, start_ts, end_ts, status) VALUES(?,?,?,?,?)",
                     (1, "x.wav", time.time() - 3600, time.time() - 3500, "done"))
        conn.commit()
    finally:
        conn.close()
    return db_path


def _seed(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            INSERT INTO trademark_entities
                (canonical_name, normalized_name, source_type, review_status, trademark_risk, ad_copy_allowed)
            VALUES
                ('CashSpot', 'cashspot', 'cfpb_complaint', 'approved', 'low', 1);

            INSERT INTO trademark_keyword_candidates
                (trademark_entity_id, keyword, normalized_keyword, variant_type, source_type, status, confidence, score, created_at)
            VALUES
                (1, 'CashSpot',            'cashspot',            'brand',     'cfpb_complaint', 'approved_seed', 1.0, 100.0, '2026-06-19T00:00:00Z'),
                (1, 'CashSpot reviews',    'cashspot reviews',    'reviews',   'cfpb_complaint', 'approved_seed', 1.0, 90.0,  '2026-06-19T00:00:00Z'),
                (1, 'TaxBust Tax Relief',  'taxbust tax relief',  'brand',     'cfpb_complaint', 'approved_seed', 1.0, 80.0,  '2026-06-19T00:00:00Z');

            INSERT INTO detections
                (chunk_id, canonical_ad_id, is_ad, ad_category, company_name, phone_number, website,
                 offer_summary, key_claims, confidence, alerted)
            VALUES
                (1, NULL, 1, 'business_funding', 'CashSpot', '8005551234', 'cashspot.com',
                 'Get fast cash today with same day funding', 'fast cash; same day funding', 0.9, 0),
                (1, NULL, 1, 'debt_relief', 'Debt Helpers', NULL, NULL,
                 'We settle your debt', 'settle debt', 0.6, 0),
                (1, NULL, 1, 'tax_relief', 'TaxBust', NULL, 'taxbust.example',
                 'Stop IRS collections on back taxes', 'back taxes; irs', 0.8, 0);

            INSERT INTO transcripts(chunk_id, text, asr_duration_ms) VALUES
                (1, 'Need cash fast? CashSpot dot com gets you approved today, direct deposit.', 90000);

            INSERT INTO keyword_hits(station_id, keyword, chunk_id, hit_ts, context_excerpt) VALUES
                (1, 'fast cash', 1, 1700000000.0, 'get fast cash today'),
                (1, 'back taxes', 1, 1700000001.0, 'settle your back taxes'),
                (1, 'credit', 1, 1700000002.0, 'repair your credit');
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# profile loading
# ---------------------------------------------------------------------------


def test_load_profile_overnight_has_phrase_lists(profile: dict) -> None:
    assert "money_problem_phrases" in profile
    assert "fast cash" in profile["money_problem_phrases"]
    assert "personal loan" in profile["loan_product_phrases"]
    assert "same day funding" in profile["approval_funding_phrases"]
    assert "dot com" in profile["brand_domain_phrases"]
    assert "tax relief" in profile["rejected_substrings"]
    assert {"brand", "domain", "money_problem", "loan_product", "approval_funding"} <= set(profile["candidate_types"])


def test_load_profile_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        hc.load_profile("does_not_exist")


def test_profile_file_on_disk_has_expected_shape() -> None:
    data = yaml.safe_load((hc.CONFIG_DIR / "harvest_profiles.yaml").read_text(encoding="utf-8"))
    assert "overnight_keyword_harvest" in data["profiles"]
    assert data["profiles"]["overnight_keyword_harvest"]["max_stations"] == 20


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_normalize_keyword_collapses_whitespace_and_case() -> None:
    assert hc.normalize_keyword("  Fast   Cash ") == "fast cash"


def test_extract_domain_strips_scheme_and_path() -> None:
    assert hc.extract_domain("https://CashSpot.com/apply?x=1") == "cashspot.com"
    assert hc.extract_domain(None) == ""
    assert hc.extract_domain("plain.word") == "plain.word"


def test_scan_text_finds_money_problem_signal(profile: dict) -> None:
    scan = hc.scan_text("Need FAST cash today with same day funding", profile)
    assert "fast cash" in scan.money_problem
    assert "same day funding" in scan.approval_funding
    assert scan.has_signal
    assert hc.classify_status(scan) == "ready"


def test_scan_text_marks_rejected_vertical(profile: dict) -> None:
    scan = hc.scan_text("Stop IRS collections on back taxes", profile)
    assert scan.rejected
    assert not scan.has_signal


def test_scan_text_ambiguous_only_no_signal(profile: dict) -> None:
    scan = hc.scan_text("we can help with your debt and bills", profile)
    assert not scan.has_signal
    assert scan.ambiguous
    assert hc.classify_status(scan) == "review"


def test_build_probe_command_shape() -> None:
    cmd = hc.build_probe_command("http://x/live", 6)
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd and "http://x/live" in cmd
    assert "-t" in cmd and "6" in cmd
    assert cmd[-2:] == ["null", "-"]


# ---------------------------------------------------------------------------
# status round-trip
# ---------------------------------------------------------------------------


def test_status_round_trip(isolated_paths: Path) -> None:
    assert hc.read_status() == {}
    hc.write_status({"state": "running", "profile": "overnight_keyword_harvest"})
    state = hc.read_status()
    assert state["state"] == "running"
    assert state["last_updated"]
    # merge, don't overwrite
    hc.write_status({"state": "stopped"})
    assert hc.read_status()["state"] == "stopped"
    assert hc.read_status()["profile"] == "overnight_keyword_harvest"


# ---------------------------------------------------------------------------
# gather_keyword_candidates (the core broadening logic)
# ---------------------------------------------------------------------------


def test_gather_candidates_surfaces_money_problem_brand_and_filters_tax(temp_db: Path, profile: dict) -> None:
    _seed(temp_db)
    conn = get_connection(temp_db)
    try:
        rows = hc.gather_keyword_candidates(conn, profile)
    finally:
        conn.close()

    by_norm_type = {(r["normalized_text"], r["candidate_type"]): r for r in rows}

    # money-problem signal from detection + transcript -> ready
    fc = by_norm_type.get(("fast cash", "money_problem"))
    assert fc is not None and fc["status"] == "ready"
    assert fc["hit_count"] >= 1

    # approval_funding from 'same day funding'
    assert ("same day funding", "approval_funding") in by_norm_type

    # brand candidate from company name
    brand = by_norm_type.get(("cashspot", "brand"))
    assert brand is not None
    assert brand["domain"] == "cashspot.com"

    # domain candidate from website
    assert ("cashspot.com", "domain") in by_norm_type

    # trademark seed brand kept; its review variant also present
    assert ("cashspot reviews", "brand") in by_norm_type

    # rejected vertical (tax/irs) must NOT appear as a brand candidate
    assert ("taxbust tax relief", "brand") not in by_norm_type

    # keyword_hit 'back taxes' (rejected) dropped; 'credit' (ambiguous) saved for review
    assert ("back taxes", "money_problem") not in by_norm_type
    review = by_norm_type.get(("credit", "money_problem"))
    assert review is not None and review["status"] == "review"

    # 'fast cash' keyword_hit also contributes -> hit_count aggregates
    assert fc["hit_count"] >= 2


def test_gather_candidates_empty_db_returns_empty(profile: dict, temp_db: Path) -> None:
    conn = get_connection(temp_db)
    try:
        rows = hc.gather_keyword_candidates(conn, profile)
    finally:
        conn.close()
    assert rows == []


# ---------------------------------------------------------------------------
# export + summary writers
# ---------------------------------------------------------------------------


def test_export_candidates_writes_csv_and_jsonl(temp_db: Path, profile: dict, isolated_paths: Path) -> None:
    _seed(temp_db)
    conn = get_connection(temp_db)
    try:
        rows = hc.gather_keyword_candidates(conn, profile)
    finally:
        conn.close()

    out = hc.export_candidates(rows)
    csv_text = out["csv"].read_text(encoding="utf-8")
    jsonl_text = out["jsonl"].read_text(encoding="utf-8")

    reader = list(csv.DictReader(csv_text.splitlines()))
    assert len(reader) == out["rows"] == len(rows)
    assert reader[0]["candidate_text"]
    assert set(reader[0].keys()) == set(hc.CSV_COLUMNS)

    json_objs = [json.loads(line) for line in jsonl_text.strip().splitlines()]
    assert len(json_objs) == len(rows)
    assert any(o["candidate_type"] == "money_problem" for o in json_objs)


def test_export_candidates_respects_limit(temp_db: Path, profile: dict, isolated_paths: Path) -> None:
    _seed(temp_db)
    conn = get_connection(temp_db)
    try:
        rows = hc.gather_keyword_candidates(conn, profile)
    finally:
        conn.close()
    out = hc.export_candidates(rows, limit=2)
    assert out["rows"] == 2


def test_write_summary_has_sections(temp_db: Path, profile: dict, isolated_paths: Path) -> None:
    _seed(temp_db)
    conn = get_connection(temp_db)
    try:
        rows = hc.gather_keyword_candidates(conn, profile)
    finally:
        conn.close()
    hc.write_status({"state": "running", "profile": "overnight_keyword_harvest"})
    md_path = hc.write_summary(rows, hc.read_status())
    text = md_path.read_text(encoding="utf-8")
    assert "# Overnight Keyword Harvest Summary" in text
    assert "## Candidates" in text
    assert "money_problem" in text
    assert "## Top candidates" in text


# ---------------------------------------------------------------------------
# CLI dispatch (no network)
# ---------------------------------------------------------------------------


def test_cli_status_runs_on_empty_status(isolated_paths: Path, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = hc.main(["--db", str(temp_db), "status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no session recorded" in out
    assert "Pipeline DB snapshot" in out


def test_cli_start_stop_round_trip(isolated_paths: Path, temp_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # avoid real network probes during start
    monkeypatch.setattr(hc, "probe_stations", lambda **kw: [{"station": "wbap-am-820", "ok": True, "url": "http://x", "display_name": "WBAP", "format": "mp3", "duration_tested_seconds": 6, "error": "", "tested_at": "now"}])
    rc = hc.main(["--db", str(temp_db), "start", "--profile", "overnight_keyword_harvest"])
    assert rc == 0
    state = hc.read_status()
    assert state["state"] == "running"
    assert state["profile"] == "overnight_keyword_harvest"
    assert state["pid"] is not None

    rc = hc.main(["--db", str(temp_db), "stop"])
    assert rc == 0
    state = hc.read_status()
    assert state["state"] == "stopped"
    assert state["pid"] is None


def test_cli_export_writes_files(isolated_paths: Path, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(temp_db)
    rc = hc.main(["--db", str(temp_db), "export"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Exported" in out
    assert (hc.EXPORTS_DIR / "overnight_keyword_candidates.csv").is_file()
    assert (hc.EXPORTS_DIR / "overnight_keyword_candidates.jsonl").is_file()
    assert (hc.EXPORTS_DIR / "overnight_keyword_summary.md").is_file()
    state = hc.read_status()
    assert state["export"]["rows"] >= 1


def test_cli_top_prints_rows(isolated_paths: Path, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(temp_db)
    rc = hc.main(["--db", str(temp_db), "top", "--limit", "5"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "money_problem" in out or "brand" in out


def test_cli_unknown_profile_returns_2(isolated_paths: Path, temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = hc.main(["--db", str(temp_db), "top", "--profile", "nope"])
    assert rc == 2
