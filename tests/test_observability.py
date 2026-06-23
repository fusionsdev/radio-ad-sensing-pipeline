"""Tests for Memory OS observability (Phase 1.95)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.main import create_app
from tests.fixtures.seed_dashboard import seed_dashboard_db
from tools.harness.runners import observability_harness
from tools.memory.metrics_collector import DAILY_DIR, METRICS_ROOT, collect_snapshot, write_daily_snapshot
from tools.memory.metrics_report import LATEST_JSON, LATEST_MD, generate_report, metrics_freshness_status
from tools.memory.vault_reader import fetch_memory_analytics


@pytest.fixture
def memory_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "obs.db"
    seed_dashboard_db(db_path, archive_dir=tmp_path / "archive")
    return TestClient(create_app(db_path=db_path))


def test_collect_snapshot_shape() -> None:
    snap = collect_snapshot()
    assert snap.date
    assert snap.memory.total_decisions >= 0
    assert snap.growth.new_decisions_7d >= 0
    assert snap.harness.pass_rate_pct >= 0
    assert snap.agents.source == "best_effort_markers"


def test_generate_report_writes_latest_files() -> None:
    payload = generate_report(write_daily=True)
    assert LATEST_JSON.exists()
    assert LATEST_MD.exists()
    assert payload["memory_growth"]["decisions"] >= 0
    assert "harness_statistics" in payload
    assert "headroom_statistics" in payload
    freshness = metrics_freshness_status()
    assert freshness["status"] == "pass"


def test_metrics_freshness_warns_when_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.memory import metrics_report as mr

    metrics_dir = tmp_path / "Metrics"
    metrics_dir.mkdir()
    latest = metrics_dir / "Latest.json"
    latest.write_text("{}", encoding="utf-8")
    old = datetime.now(tz=UTC) - timedelta(days=10)
    ts = old.timestamp()
    import os

    os.utime(latest, (ts, ts))
    monkeypatch.setattr(mr, "METRICS_ROOT", metrics_dir)
    monkeypatch.setattr(mr, "LATEST_JSON", latest)
    status = metrics_freshness_status()
    assert status["status"] == "warning"
    assert status["passed"] is False


def test_observability_harness_passes() -> None:
    result = observability_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]
    assert result.metrics.get("observability_status") in {"pass", "warning"}
    assert result.metrics.get("analytics_report_ok") is True


def test_observability_harness_fails_without_metrics_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.harness.runners import observability_harness as oh
    from tools.memory import metrics_collector as mc
    from tools.memory import metrics_report as mr

    fake_root = tmp_path / "Metrics"
    monkeypatch.setattr(mc, "METRICS_ROOT", fake_root)
    monkeypatch.setattr(mc, "DAILY_DIR", fake_root / "Daily")
    monkeypatch.setattr(mr, "METRICS_ROOT", fake_root)
    monkeypatch.setattr(mr, "LATEST_JSON", fake_root / "Latest.json")
    monkeypatch.setattr(mr, "LATEST_MD", fake_root / "Latest.md")
    monkeypatch.setattr(oh, "METRICS_ROOT", fake_root)
    monkeypatch.setattr(oh, "DAILY_DIR", fake_root / "Daily")
    monkeypatch.setattr(oh, "LATEST_JSON", fake_root / "Latest.json")
    monkeypatch.setattr(oh, "LATEST_MD", fake_root / "Latest.md")

    def _fail_generate(**_kwargs: object) -> dict:
        raise OSError("simulated failure")

    monkeypatch.setattr(oh, "generate_report", _fail_generate)
    result = oh.run()
    assert not result.passed
    assert result.metrics["observability_status"] == "fail"


def test_memory_analytics_api(memory_client: TestClient) -> None:
    response = memory_client.get("/api/memory/analytics")
    assert response.status_code == 200
    body = response.json()
    assert "memory_growth" in body
    assert "harness_statistics" in body
    assert "headroom_statistics" in body
    assert "growth_7d" in body


def test_fetch_memory_analytics_reads_latest() -> None:
    generate_report(write_daily=True)
    data = fetch_memory_analytics()
    assert data.get("memory_health")
    assert "memory_growth" in data


def test_daily_snapshot_roundtrip() -> None:
    snap = collect_snapshot()
    path = write_daily_snapshot(snap)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["date"] == snap.date
    assert loaded["memory"]["total_decisions"] == snap.memory.total_decisions


def test_metrics_directory_structure() -> None:
    generate_report(write_daily=True)
    assert METRICS_ROOT.is_dir()
    assert (METRICS_ROOT / "Daily").is_dir()
    assert (METRICS_ROOT / "Weekly").is_dir()
    assert (METRICS_ROOT / "Monthly").is_dir()
    assert len(list(DAILY_DIR.glob("*-metrics.json"))) >= 1