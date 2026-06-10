"""Tests for pydantic models and LLM extraction schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.models import (
    AdExtraction,
    AdExtractionWithMetadata,
    ChunkStatus,
    Detection,
    detection_from_extraction,
)


def test_ad_extraction_validates_core_fields() -> None:
    extraction = AdExtraction(
        is_ad=True,
        ad_category="business_loan",
        company_name="Acme Funding",
        phone_number="8005551234",
        website="https://acme.example",
        offer_summary="Fast funding up to $500k",
        key_claims=["no collateral", "same-day approval"],
        confidence=0.92,
    )
    assert extraction.is_ad is True
    assert extraction.confidence == 0.92


def test_ad_extraction_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        AdExtraction(is_ad=False, confidence=1.5)


def test_metadata_not_in_llm_schema() -> None:
    fields = set(AdExtraction.model_fields)
    assert "station" not in fields
    assert "timestamp" not in fields


def test_metadata_model_extends_extraction() -> None:
    row = AdExtractionWithMetadata(
        is_ad=True,
        confidence=0.8,
        station="news-talk",
        timestamp=1710000000.0,
    )
    assert row.station == "news-talk"
    assert row.timestamp == 1710000000.0


def test_detection_from_extraction() -> None:
    extraction = AdExtraction(
        is_ad=True,
        company_name="Acme",
        key_claims=["low rates"],
        confidence=0.85,
    )
    detection = detection_from_extraction(chunk_id=42, extraction=extraction)
    assert detection.chunk_id == 42
    assert detection.is_ad is True
    assert detection.company_name == "Acme"
    assert detection.key_claims == ["low rates"]
    assert detection.alerted is False


def test_chunk_status_enum() -> None:
    assert ChunkStatus.PENDING.value == "pending"
    assert Detection.model_fields["alerted"].default is False
