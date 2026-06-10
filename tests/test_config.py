"""Tests for YAML and environment config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import load_settings, load_stations, load_telegram_settings


def test_load_stations_from_repo_config() -> None:
    stations = load_stations()
    assert len(stations) >= 1
    station = stations[0]
    assert station.name
    assert station.url
    assert isinstance(station.enabled, bool)


def test_load_settings_from_repo_config() -> None:
    settings = load_settings()
    assert settings.chunk_len == 90
    assert settings.overlap == 7
    assert settings.retention_hours == 48
    assert settings.dedup_window_days == 7
    assert settings.asr_model == "medium.en"
    assert settings.asr_compute_type == "int8_float16"
    assert settings.dashboard_host == "127.0.0.1"
    assert settings.dashboard_port == 8080
    assert settings.chunks_dir == "data/chunks"


def test_load_settings_chunks_dir_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUNKS_DIR", "/app/chunks")
    settings = load_settings()
    assert settings.chunks_dir == "/app/chunks"


def test_load_settings_dashboard_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("DASHBOARD_PORT", "9000")
    settings = load_settings()
    assert settings.dashboard_host == "0.0.0.0"
    assert settings.dashboard_port == 9000


def test_load_settings_asr_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_MODEL", "distil-large-v3")
    monkeypatch.setenv("ASR_COMPUTE_TYPE", "int8")
    settings = load_settings()
    assert settings.asr_model == "distil-large-v3"
    assert settings.asr_compute_type == "int8"


def test_load_stations_from_custom_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "stations.yaml"
    yaml_path.write_text(
        """
stations:
  - name: test-fm
    url: https://radio.example/stream
    format: aac
    enabled: true
""".strip(),
        encoding="utf-8",
    )
    stations = load_stations(yaml_path)
    assert len(stations) == 1
    assert stations[0].name == "test-fm"
    assert stations[0].format == "aac"
    assert stations[0].enabled is True


def test_telegram_settings_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    settings = load_telegram_settings()
    assert settings.telegram_bot_token is None
    assert settings.telegram_chat_id is None
