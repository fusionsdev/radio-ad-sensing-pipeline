"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging
from io import StringIO

from shared.logging import setup_logging


def test_json_log_includes_service_name() -> None:
    stream = StringIO()
    logger = setup_logging("ingestor", stream=stream)
    logger.info("station connected", extra={"station": "news-talk"})

    payload = json.loads(stream.getvalue().strip())
    assert payload["service"] == "ingestor"
    assert payload["message"] == "station connected"
    assert payload["level"] == "INFO"
    assert payload["station"] == "news-talk"
