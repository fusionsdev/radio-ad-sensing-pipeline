"""WP-11b extraction eval-set tests for loan-ad-style transcript fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker.extract import OllamaExtractor, normalize_phone_number


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "extraction_eval"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"


@dataclass(frozen=True)
class EvalFixture:
    fixture_id: str
    transcript: str
    expected_is_ad: bool
    expected_company_name: str | None
    expected_phone: str | None
    mock_response: dict[str, Any]


def _load_eval_fixtures() -> list[EvalFixture]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    fixtures: list[EvalFixture] = []
    for raw in manifest["fixtures"]:
        transcript_path = FIXTURE_DIR / raw["transcript_file"]
        fixtures.append(
            EvalFixture(
                fixture_id=raw["id"],
                transcript=transcript_path.read_text(encoding="utf-8").strip(),
                expected_is_ad=raw["expected"]["is_ad"],
                expected_company_name=raw["expected"]["company_name"],
                expected_phone=raw["expected"]["phone"],
                mock_response=raw["mock_response"],
            )
        )
    return fixtures


def _company_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in value)
    return {token for token in cleaned.split() if token not in {"llc", "co", "inc", "corp", "company"}}


def _company_match(actual: str | None, expected: str | None) -> bool:
    if expected is None:
        return actual is None
    actual_tokens = _company_tokens(actual)
    expected_tokens = _company_tokens(expected)
    return bool(expected_tokens) and expected_tokens.issubset(actual_tokens)


class _MockOllamaHTTP:
    def __init__(self, response_payloads: list[dict[str, Any]]) -> None:
        self._responses = list(response_payloads)
        self.calls: list[dict[str, Any]] = []

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {"response": json.dumps(self._responses.pop(0))}


EVAL_FIXTURES = _load_eval_fixtures()


def test_extraction_eval_manifest_has_phase_11b_coverage() -> None:
    positives = [fixture for fixture in EVAL_FIXTURES if fixture.expected_is_ad]
    negatives = [fixture for fixture in EVAL_FIXTURES if not fixture.expected_is_ad]

    assert len(positives) >= 4
    assert len(negatives) >= 3
    assert all(fixture.transcript for fixture in EVAL_FIXTURES)


def test_extraction_eval_phone_normalization_matches_ground_truth() -> None:
    fixtures_with_phone = [fixture for fixture in EVAL_FIXTURES if fixture.expected_phone]

    assert fixtures_with_phone
    for fixture in fixtures_with_phone:
        normalized = normalize_phone_number(fixture.mock_response["phone_number"])
        assert normalized == fixture.expected_phone, fixture.fixture_id


def test_extraction_eval_mock_extractor_meets_scoring_rubric() -> None:
    client = _MockOllamaHTTP([fixture.mock_response for fixture in EVAL_FIXTURES])
    extractor = OllamaExtractor(model="qwen-eval-mock", http_client=client)

    scorecards: list[tuple[str, bool, bool, bool]] = []
    for fixture in EVAL_FIXTURES:
        extraction = extractor.extract(fixture.transcript)
        is_ad_correct = extraction.is_ad is fixture.expected_is_ad
        company_correct = _company_match(extraction.company_name, fixture.expected_company_name)
        phone_correct = normalize_phone_number(extraction.phone_number) == fixture.expected_phone
        scorecards.append((fixture.fixture_id, is_ad_correct, company_correct, phone_correct))

    failures = [
        fixture_id
        for fixture_id, is_ad_correct, company_correct, phone_correct in scorecards
        if not is_ad_correct or not company_correct or not phone_correct
    ]

    assert not failures, f"extraction eval rubric failed: {failures}"
    assert len(client.calls) == len(EVAL_FIXTURES)
