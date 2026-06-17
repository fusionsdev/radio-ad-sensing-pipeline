"""Load stations and pipeline settings from YAML + environment."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.models import LoanKeywordEntry, LoanKeywordsFile, PipelineSettings, StationConfig, StationsFile, VerticalKeywordsFile

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")


def load_stations(path: Path | None = None) -> list[StationConfig]:
    config_path = path or CONFIG_DIR / "stations.yaml"
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return StationsFile.model_validate(data).stations


def _normalize_loan_keywords_data(data: object) -> object:
    """Accept v2 {phrase, confidence} entries and legacy plain strings."""
    if not isinstance(data, dict):
        return data
    raw_keywords = data.get("keywords")
    if not isinstance(raw_keywords, list):
        return data
    normalized: list[object] = []
    for item in raw_keywords:
        if isinstance(item, str):
            normalized.append({"phrase": item.strip(), "confidence": 0.7})
        else:
            normalized.append(item)
    return {**data, "keywords": normalized}


def load_vertical_keywords(path: Path | None = None) -> VerticalKeywordsFile:
    """Load vertical-grouped keyword config from YAML."""
    from shared.verticals import load_vertical_keywords as _load

    return _load(path)


def load_loan_keywords(path: Path | None = None) -> list[LoanKeywordEntry]:
    """Load all keyword phrases for transcript scanning (vertical config first)."""
    from shared.verticals import flatten_vertical_keywords, load_vertical_keywords

    if path is None:
        vertical_path = CONFIG_DIR / "vertical_keywords.yaml"
        if vertical_path.is_file():
            return flatten_vertical_keywords(load_vertical_keywords(vertical_path))

    config_path = path or CONFIG_DIR / "loan_keywords.yaml"
    if not config_path.is_file():
        return []
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return LoanKeywordsFile.model_validate(_normalize_loan_keywords_data(data)).keywords


def load_settings(path: Path | None = None) -> PipelineSettings:
    config_path = path or CONFIG_DIR / "settings.yaml"
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    settings = PipelineSettings.model_validate(data)

    # Docker compose sets DASHBOARD_HOST/PORT; env overrides yaml at runtime.
    updates: dict[str, str | int] = {}
    if host := os.environ.get("DASHBOARD_HOST"):
        updates["dashboard_host"] = host
    if port := os.environ.get("DASHBOARD_PORT"):
        updates["dashboard_port"] = int(port)
    if chunks_dir := os.environ.get("CHUNKS_DIR"):
        updates["chunks_dir"] = chunks_dir
    if asr_model := os.environ.get("ASR_MODEL"):
        updates["asr_model"] = asr_model
    if asr_compute_type := os.environ.get("ASR_COMPUTE_TYPE"):
        updates["asr_compute_type"] = asr_compute_type
    if updates:
        settings = settings.model_copy(update=updates)

    return settings


def load_telegram_settings() -> TelegramSettings:
    return TelegramSettings()
