"""Smoke tests for RadioSense Memory OS harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.harness.lib.common import MANDATORY_MEMORY_FILES, build_report
from tools.harness.runners import (
    classifier_harness,
    dashboard_harness,
    decision_harness,
    hermes_harness,
    memory_harness,
    station_harness,
)
from tools.memory.decision_logger import log_decision
from tools.memory.incident_logger import log_incident
from tools.memory.memory_report import build_memory_health
from tools.memory.station_logger import log_station_change
from tools.memory.zvec_hooks import build_index_manifest


@pytest.mark.parametrize("path", MANDATORY_MEMORY_FILES)
def test_mandatory_memory_files_exist(path: Path) -> None:
    assert path.exists(), path.name


def test_classifier_harness_passes() -> None:
    result = classifier_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]


def test_dashboard_harness_passes() -> None:
    result = dashboard_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]


def test_station_harness_passes() -> None:
    result = station_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]


def test_hermes_harness_passes() -> None:
    result = hermes_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]


def test_build_report_shape() -> None:
    results = [classifier_harness.run(), station_harness.run()]
    report = build_report(results)
    assert "timestamp" in report
    assert report["status"] in {"pass", "fail"}
    assert "overnight_readiness" in report
    assert "failed_checks" in report


def test_zvec_hooks_manifest() -> None:
    manifest = build_index_manifest()
    assert manifest["phase"] == 1
    assert manifest["zvec_enabled"] is False
    assert manifest["markdown_count"] >= 5


def test_decision_harness_passes() -> None:
    result = decision_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]


def test_memory_harness_passes() -> None:
    result = memory_harness.run()
    assert result.passed, [c.detail for c in result.failed_checks()]


def test_memory_health_report_shape() -> None:
    health = build_memory_health()
    assert "subchecks" in health
    assert health["subchecks"]["core_files"] == "pass"


def test_decision_logger_creates_file(tmp_path, monkeypatch) -> None:
    from tools.memory import _common

    decisions = tmp_path / "Decisions"
    monkeypatch.setattr(_common, "DECISIONS_DIR", decisions)
    monkeypatch.setattr("tools.memory.decision_logger.DECISIONS_DIR", decisions)

    path = log_decision(
        "test-decision",
        context="unit test",
        decision="noop",
        related_files=["scripts/loan_classifier.py"],
        date="2099-01-01",
    )
    assert path.exists()
    assert "unit test" in path.read_text(encoding="utf-8")


def test_incident_logger_creates_file(tmp_path, monkeypatch) -> None:
    from tools.memory import _common

    incidents = tmp_path / "Incidents"
    monkeypatch.setattr(_common, "INCIDENTS_DIR", incidents)
    monkeypatch.setattr("tools.memory.incident_logger.INCIDENTS_DIR", incidents)

    path = log_incident("api-500", symptoms="dashboard 500", date="2099-01-01")
    assert path.exists()
    assert "dashboard 500" in path.read_text(encoding="utf-8")


def test_station_logger_creates_file(tmp_path, monkeypatch) -> None:
    from tools.memory import _common

    stations = tmp_path / "Stations"
    monkeypatch.setattr(_common, "STATIONS_DIR", stations)
    monkeypatch.setattr("tools.memory.station_logger.STATIONS_DIR", stations)

    path = log_station_change("WBAP", "keep", reasoning="2 loan advertisers", date="2099-01-01")
    assert path.name == "WBAP.md"
    assert "keep" in path.read_text(encoding="utf-8")