"""Pydantic models mirroring SQLite tables and the LLM extraction schema."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChunkStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    DROPPED = "dropped"


class Station(BaseModel):
    id: int | None = None
    name: str
    url: str
    format: str | None = None
    enabled: bool = True


class CanonicalAd(BaseModel):
    id: int | None = None
    company_name: str | None = None
    phone_norm: str | None = None
    category: str | None = None
    first_seen: float
    last_seen: float
    airing_count: int = 0
    archived_audio_path: str | None = None


class Chunk(BaseModel):
    id: int | None = None
    station_id: int
    path: str
    start_ts: float
    end_ts: float
    status: ChunkStatus = ChunkStatus.PENDING
    error: str | None = None
    known_ad_id: int | None = None


class Transcript(BaseModel):
    id: int | None = None
    chunk_id: int
    text: str
    asr_duration_ms: int | None = None
    segments_json: str | None = None


class Detection(BaseModel):
    id: int | None = None
    chunk_id: int
    canonical_ad_id: int | None = None
    is_ad: bool
    ad_category: str | None = None
    company_name: str | None = None
    phone_number: str | None = None
    website: str | None = None
    offer_summary: str | None = None
    key_claims: list[str] = Field(default_factory=list)
    confidence: float | None = None
    alerted: bool = False


class Gap(BaseModel):
    id: int | None = None
    station_id: int
    start_ts: float
    end_ts: float | None = None
    reason: str


class Fingerprint(BaseModel):
    id: int | None = None
    canonical_ad_id: int
    chromaprint_vector: bytes
    duration: float


class StatusEntry(BaseModel):
    key: str
    value: str
    updated_at: float


class AdExtraction(BaseModel):
    """LLM extraction schema — station/timestamp are metadata, not in this schema."""

    is_ad: bool
    ad_category: str | None = None
    company_name: str | None = None
    phone_number: str | None = None
    website: str | None = None
    offer_summary: str | None = None
    key_claims: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class AdExtractionWithMetadata(AdExtraction):
    """Extraction result enriched with chunk metadata before persistence."""

    station: str
    timestamp: float


class StationConfig(BaseModel):
    name: str
    url: str
    format: str | None = None
    enabled: bool = True


class StationsFile(BaseModel):
    stations: list[StationConfig]


class PipelineSettings(BaseModel):
    chunk_len: int = 90
    overlap: int = 7
    retention_hours: int = 48
    dedup_window_days: int = 7
    confidence_threshold: float = 0.7
    fuzzy_match_threshold: int = 85
    queue_max_hours: int = 2
    station_down_alert_minutes: int = 15
    same_station_airing_window_seconds: int = 180
    asr_model: str = "medium.en"
    asr_compute_type: str = "int8_float16"
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8080
    db_path: str = "data/pipeline.db"
    chunks_dir: str = "data/chunks"
    # Ingestor resilience — fast retry before exponential backoff
    ingest_immediate_retries: int = 3
    ingest_immediate_retry_delay_sec: float = 0.5
    ingest_backoff_initial_sec: float = 1.0
    ingest_backoff_max_sec: float = 30.0


def detection_from_extraction(
    chunk_id: int,
    extraction: AdExtraction,
    *,
    canonical_ad_id: int | None = None,
) -> Detection:
    """Build a Detection row from validated LLM extraction output."""
    return Detection(
        chunk_id=chunk_id,
        canonical_ad_id=canonical_ad_id,
        is_ad=extraction.is_ad,
        ad_category=extraction.ad_category,
        company_name=extraction.company_name,
        phone_number=extraction.phone_number,
        website=extraction.website,
        offer_summary=extraction.offer_summary,
        key_claims=extraction.key_claims,
        confidence=extraction.confidence,
    )


def parse_key_claims_json(raw: str | None) -> list[str]:
    """Parse key_claims stored as JSON text in SQLite."""
    if not raw:
        return []
    data: Any = json.loads(raw)
    if isinstance(data, list):
        return [str(item) for item in data]
    return []
