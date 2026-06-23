"""Unit tests for memory analytics categorization."""

from __future__ import annotations

from tools.memory.analytics import classify_decision, classify_incident


def test_classify_incident_docker() -> None:
    assert classify_incident("memory-api-404-docker", "radio-dashboard container old image") == "Docker"


def test_classify_incident_other() -> None:
    assert classify_incident("unknown issue", "something vague happened") == "Other"


def test_classify_decision_memory_os() -> None:
    assert classify_decision("Memory OS Phase 1.5", "project-memory harness") == "Memory OS"


def test_classify_decision_dashboard() -> None:
    assert classify_decision("memory dashboard", "radiosense-aistudio routing") == "Dashboard"