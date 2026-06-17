"""Tests for WP-4 LLM extraction prompt, schema, and phone normalization."""

from __future__ import annotations

import json
from typing import Any

import pytest

from shared.models import AdExtraction
from worker.extract import (
    OllamaExtractor,
    build_extraction_prompt,
    extraction_json_schema,
    normalize_phone_number,
)


def test_normalize_phone_number_handles_spelled_and_vanity_numbers() -> None:
    assert normalize_phone_number("Call eight hundred five five five one two one two") == "8005551212"
    assert normalize_phone_number("1-800-CASH-NOW") == "18002274669"
    assert normalize_phone_number("(212) 555-0199") == "2125550199"


def test_normalize_phone_number_rejects_word_only_vanity_garbage() -> None:
    """Spelled toll-free prefix must not fall through to T9 on English prose."""
    assert normalize_phone_number("one eight hundred tax help") == "1800"
    assert normalize_phone_number("eight hundred") == "800"
    assert normalize_phone_number("eight hundred five five five") == "800555"
    assert normalize_phone_number("call us about loans today") is None


def test_prompt_few_shot_example_three_uses_normalized_phone() -> None:
    prompt = build_extraction_prompt("placeholder")
    assert '"phone_number": "8008294357"' in prompt
    assert '"phone_number": "one eight hundred tax help"' not in prompt


def test_prompt_contains_ad_signal_cues_and_excludes_metadata_fields() -> None:
    prompt = build_extraction_prompt(
        "Funding is available now. Call 800-555-1212 for a free quote.",
    )

    lowered = prompt.lower()
    assert "call to action" in lowered
    assert "phone" in lowered
    assert "sponsored" in lowered
    assert "few-shot" in lowered or "examples" in lowered
    assert "station" not in AdExtraction.model_fields
    assert "timestamp" not in AdExtraction.model_fields


def test_schema_is_strict_and_only_contains_llm_fields() -> None:
    schema = extraction_json_schema()
    properties = set(schema["properties"])

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "station" not in properties
    assert "timestamp" not in properties
    assert {"is_ad", "ad_category", "confidence"}.issubset(properties)


class FakeOllamaHTTP:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return self.responses.pop(0)


def test_ollama_extractor_retries_invalid_json_and_normalizes_phone() -> None:
    client = FakeOllamaHTTP(
        [
            {"response": "not json"},
            {
                "response": json.dumps(
                    {
                        "is_ad": True,
                        "ad_category": "business_funding",
                        "company_name": "Rapid Capital",
                        "phone_number": "eight hundred five five five one two one two",
                        "website": None,
                        "offer_summary": "Working capital up to $500k",
                        "key_claims": ["same-day funding", "bad credit considered"],
                        "confidence": 0.91,
                    }
                )
            },
        ]
    )
    extractor = OllamaExtractor(model="qwen-test", http_client=client)

    result = extractor.extract("Need cash for your business? Call eight hundred five five five one two one two.")

    assert result.is_ad is True
    assert result.phone_number == "8005551212"
    assert result.company_name == "Rapid Capital"
    assert len(client.calls) == 2
    payload = client.calls[0]
    assert payload["model"] == "qwen-test"
    assert payload["format"]["additionalProperties"] is False
    assert payload["stream"] is False


def test_ollama_extractor_raises_after_retry_exhausted() -> None:
    client = FakeOllamaHTTP([{"response": "{}"}, {"response": "also bad"}])
    extractor = OllamaExtractor(http_client=client)

    with pytest.raises(ValueError):
        extractor.extract("A normal talk segment about mortgage rates.")


def test_ollama_extractor_classifies_senator_loan_talk_as_non_ad() -> None:
    transcript = (
        "The senator discussed small-business lending standards and today's interest-rate outlook "
        "while reviewing federal loan guarantee programs."
    )
    client = FakeOllamaHTTP(
        [
            {
                "response": json.dumps(
                    {
                        "is_ad": False,
                        "ad_category": None,
                        "company_name": None,
                        "phone_number": None,
                        "website": None,
                        "offer_summary": None,
                        "key_claims": [],
                        "confidence": 0.88,
                    }
                )
            }
        ]
    )
    extractor = OllamaExtractor(model="qwen-test", http_client=client)

    result = extractor.extract(transcript)

    assert result.is_ad is False
    assert result.phone_number is None
    assert len(client.calls) == 1


def test_normalize_phone_prefers_literal_digits_over_spelled_words() -> None:
    # A real digit number must win even when surrounded by number-words/prose,
    # so stray spelled digits cannot fabricate a phone and merge unrelated ads.
    assert normalize_phone_number("800-555-1212") == "8005551212"
    assert normalize_phone_number("(800) 555-1212") == "8005551212"
    assert normalize_phone_number("1-800-829-4357") == "18008294357"
