"""Load stations and pipeline settings from YAML + environment."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.models import PipelineSettings, StationConfig, StationsFile

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
