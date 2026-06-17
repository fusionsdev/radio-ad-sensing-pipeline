"""Tests for YAML and environment config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import load_loan_keywords, load_settings, load_stations, load_telegram_settings


def test_load_stations_from_repo_config() -> None:
    stations = load_stations()
    assert len(stations) >= 1
    station = stations[0]
    assert station.name
    assert station.url
    assert isinstance(station.enabled, bool)


def test_load_stations_have_display_names() -> None:
    stations = load_stations()
    wbap = next(s for s in stations if s.name == "wbap-am-820")
    assert wbap.display_name == "WBAP 820 AM — Dallas–Fort Worth, TX"


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


def test_load_loan_keywords_from_repo_config() -> None:
    keywords = load_loan_keywords()
    phrases = {entry.phrase for entry in keywords}
    assert "business funding" in phrases
    assert "tax debt relief" in phrases
    assert all(0.0 <= entry.confidence <= 1.0 for entry in keywords)


def test_load_loan_keywords_legacy_string_format(tmp_path: Path) -> None:
    path = tmp_path / "loan_keywords.yaml"
    path.write_text("keywords:\n  - hard money\n  - business funding\n", encoding="utf-8")
    keywords = load_loan_keywords(path)
    assert [entry.phrase for entry in keywords] == ["hard money", "business funding"]
    assert keywords[0].confidence == 0.7


def test_load_loan_keywords_missing_file_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.config.CONFIG_DIR",
        tmp_path,
    )
    assert load_loan_keywords() == []


def test_telegram_settings_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    from shared.config import TelegramSettings

    settings = TelegramSettings(_env_file=None)
    assert settings.telegram_bot_token is None
    assert settings.telegram_chat_id is None
