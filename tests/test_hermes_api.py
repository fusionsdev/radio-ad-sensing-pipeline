"""Tests for Hermes analyze API."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.hermes_client import MAX_HERMES_PROMPT_CHARS, analyze_prompt
from dashboard.main import create_app
from tests.fixtures.seed_dashboard import seed_dashboard_db


@pytest.fixture
def client(tmp_path):
    archive = tmp_path / "ad_archive"
    db_path = tmp_path / "seeded.db"
    seed_dashboard_db(db_path, archive_dir=archive)
    return TestClient(create_app(db_path=db_path))


def test_analyze_disabled_returns_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "disabled")
    result = analyze_prompt("what-next", "Test prompt", {"source": "radiosense"})
    assert result["ok"] is False
    assert result["answer"] == ""
    assert result["provider"] == "local_hermes"
    assert result["error"] == "Local Hermes is not configured or unavailable"
    assert "GEMINI" not in json.dumps(result)


def test_analyze_oversized_prompt_returns_clean_error(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "local_cli")
    prompt = "x" * (MAX_HERMES_PROMPT_CHARS + 1)
    result = analyze_prompt("what-next", prompt)
    assert result["ok"] is False
    assert result["error"] == "Prompt too large"


def test_analyze_cli_missing_returns_clean_error(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "local_cli")
    monkeypatch.setenv("HERMES_COMMAND", "definitely-not-a-real-hermes-binary")
    result = analyze_prompt("what-next", "Test prompt")
    assert result["ok"] is False
    assert result["error"] == "Local Hermes is not configured or unavailable"


def test_analyze_mocked_local_cli_returns_answer(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "local_cli")

    with patch(
        "dashboard.hermes_client.call_local_hermes_cli",
        return_value="Reduce active stations and inspect worker throughput.",
    ):
        result = analyze_prompt(
            "what-next",
            "Given queue pending 80 and drop ratio 2.2x, what should I do next?",
        )

    assert result["ok"] is True
    assert "Reduce active stations" in result["answer"]
    assert result["provider"] == "local_hermes"
    assert result["model"] == "hermes-local"


def test_analyze_mocked_local_http_returns_answer(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "local_http")
    monkeypatch.setenv("HERMES_BASE_URL", "http://127.0.0.1:8791")

    with patch(
        "dashboard.hermes_client.call_local_hermes_http",
        return_value="Prioritize queue relief.",
    ):
        result = analyze_prompt("what-next", "Test prompt")

    assert result["ok"] is True
    assert result["answer"] == "Prioritize queue relief."
    assert result["provider"] == "local_hermes"


def test_analyze_cli_timeout_returns_clean_error(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "local_cli")

    with patch(
        "dashboard.hermes_client.call_local_hermes_cli",
        side_effect=TimeoutError,
    ):
        result = analyze_prompt("what-next", "Test prompt")

    assert result["ok"] is False
    assert result["error"] == "Local Hermes is not configured or unavailable"


def test_hermes_api_endpoint_disabled(client, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "disabled")
    response = client.post(
        "/api/hermes/analyze",
        json={
            "command": "what-next",
            "prompt": "Test prompt",
            "context": {"source": "radiosense"},
        },
    )
    assert response.status_code == 503
    data = response.json()
    assert data["ok"] is False
    assert data["provider"] == "local_hermes"
    assert data["error"] == "Local Hermes is not configured or unavailable"
    assert "GEMINI" not in response.text


def test_hermes_api_endpoint_mocked_success(client, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PROVIDER", "local_http")
    monkeypatch.setenv("HERMES_BASE_URL", "http://127.0.0.1:8791")

    with patch(
        "dashboard.hermes_client.call_local_hermes_http",
        return_value="Prioritize queue relief.",
    ):
        response = client.post(
            "/api/hermes/analyze",
            json={
                "command": "what-next",
                "prompt": "Given queue pending 80 and drop ratio 2.2x, what should I do next?",
                "context": {"source": "radiosense"},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "Prioritize queue relief." in data["answer"]
    assert data["provider"] == "local_hermes"
    assert "GEMINI" not in response.text