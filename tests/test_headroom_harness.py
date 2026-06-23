"""Tests for Headroom harness (Memory OS Phase 1.9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.harness.runners import headroom_harness


def test_headroom_config_exists() -> None:
    assert headroom_harness.HEADROOM_CONFIG_DIR.is_dir()
    for name in headroom_harness.REQUIRED_CONFIG_FILES:
        assert (headroom_harness.HEADROOM_CONFIG_DIR / name).exists(), name


def test_headroom_harness_passes_or_warns_when_proxy_offline() -> None:
    result = headroom_harness.run()
    status = result.metrics.get("headroom_status")
    assert status in {"pass", "warning", "fail"}
    if status == "warning":
        assert result.passed
        assert result.metrics.get("proxy_reachable") is False or result.metrics.get("proxy_healthy") is False
    if status == "pass":
        assert result.passed
        assert result.metrics.get("config_ok")
        assert result.metrics.get("agent_files_ok")


def test_missing_proxy_generates_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(headroom_harness, "_port_reachable", lambda *_a, **_k: False)
    result = headroom_harness.run()
    assert result.metrics["headroom_status"] == "warning"
    assert result.passed
    proxy_check = next(c for c in result.checks if c.name == "proxy_port")
    assert not proxy_check.passed


def test_missing_config_generates_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_dir = tmp_path / "no-headroom"
    monkeypatch.setattr(headroom_harness, "HEADROOM_CONFIG_DIR", missing_dir)
    result = headroom_harness.run()
    assert result.metrics["headroom_status"] == "fail"
    assert not result.passed
    config_check = next(c for c in result.checks if c.name == "config_dir")
    assert not config_check.passed


def test_health_check_parses_healthy_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return b'{"status": "healthy"}'

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(headroom_harness.urllib.request, "urlopen", lambda *_a, **_k: FakeResponse())
    ok, detail = headroom_harness._health_check("http://127.0.0.1:8787/health")
    assert ok
    assert detail == "healthy"


def test_health_check_fails_on_unhealthy_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return b'{"status": "degraded"}'

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(headroom_harness.urllib.request, "urlopen", lambda *_a, **_k: FakeResponse())
    ok, detail = headroom_harness._health_check("http://127.0.0.1:8787/health")
    assert not ok
    assert "degraded" in detail


def test_format_headroom_status_section() -> None:
    lines = headroom_harness.format_headroom_status_section(
        {
            "headroom_status": "warning",
            "proxy_reachable": False,
            "proxy_healthy": False,
            "agent_files_ok": True,
            "config_ok": True,
        }
    )
    text = "\n".join(lines)
    assert "Headroom Status" in text
    assert "WARNING" in text
    assert "Agent Files" in text