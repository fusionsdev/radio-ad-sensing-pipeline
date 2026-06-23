"""Smoke tests for RadioSense Memory OS harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.harness.lib.common import MANDATORY_MEMORY_FILES, build_report
from tools.harness.runners import (
    classifier_harness,
    dashboard_harness,
    hermes_harness,
    station_harness,
)
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