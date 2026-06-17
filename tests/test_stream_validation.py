from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from scripts import browser_resolve_streams as browser_resolve
from scripts import validate_streams


def test_build_ffmpeg_command_includes_browser_headers() -> None:
    command = validate_streams.build_ffmpeg_command(
        "https://example.com/live.m3u8",
        10,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Referer": "https://example.com/listen-live",
            "Origin": "https://example.com",
            "Accept": "*/*",
            "Icy-MetaData": "1",
        },
    )

    assert command[:2] == ["ffmpeg", "-hide_banner"]
    assert "-user_agent" in command
    headers = command[command.index("-headers") + 1]
    assert "Referer: https://example.com/listen-live" in headers
    assert "Origin: https://example.com" in headers
    assert "Accept: */*" in headers
    assert "Icy-MetaData: 1" in headers


def test_validate_candidate_marks_header_required_when_headers_fix_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = validate_streams.StreamCandidate(
        station_id="kbxx",
        station_name="KBXX",
        market="Houston, TX",
        format="Urban / Hip-Hop",
        url="https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac",
        raw={"station_id": "kbxx", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac"},
        ffmpeg_headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://theboxhouston.com/listen-live/",
            "Origin": "https://theboxhouston.com",
            "Accept": "*/*",
            "Icy-MetaData": "1",
        },
    )

    attempts = iter(
        [
            (1, "[https @ 1] HTTP error 403 Forbidden", []),
            (0, "", [candidate.url]),
        ]
    )

    def fake_run_ffmpeg(*args, **kwargs):
        return next(attempts)

    monkeypatch.setattr(validate_streams, "_run_ffmpeg", fake_run_ffmpeg)

    result = validate_streams.validate_candidate(candidate, 10, 30)

    assert result["pre_header_status"] == "FAIL"
    assert result["header_attempt_status"] == "PASS"
    assert result["ffmpeg_status"] == "HEADER_REQUIRED"
    assert result["final_status"] == "HEADER_REQUIRED"
    assert result["tested_with_headers"] is True


def test_validate_candidate_marks_tokenized_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = validate_streams.StreamCandidate(
        station_id="tok",
        station_name="Tokenized",
        market="Test",
        format="Test",
        url="https://example.com/live.m3u8?token=abc123",
        raw={"station_id": "tok", "url": "https://example.com/live.m3u8?token=abc123"},
    )

    monkeypatch.setattr(validate_streams, "_run_ffmpeg", lambda *args, **kwargs: (0, "", [candidate.url]))

    result = validate_streams.validate_candidate(candidate, 10, 30)

    assert result["ffmpeg_status"] == "TOKENIZED"
    assert result["final_status"] == "TOKENIZED"


def test_browser_candidate_filtering_keeps_media_urls() -> None:
    text = """
    https://example.com/not-media
    https://example.com/live.m3u8
    https://example.com/stream.mp3
    https://example.com/file.aac
    https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac
    https://example.com/path?token=abc
    """

    candidates = browser_resolve.extract_candidate_urls(text)

    assert "https://example.com/live.m3u8" in candidates
    assert "https://example.com/stream.mp3" in candidates
    assert "https://example.com/file.aac" in candidates
    assert "https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac" in candidates
    assert "https://example.com/not-media" not in candidates


def test_yaml_ffmpeg_headers_round_trip() -> None:
    payload = {
        "stations": [
            {
                "id": "kbxx",
                "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac",
                "ffmpeg_headers": {
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://theboxhouston.com/listen-live/",
                    "Origin": "https://theboxhouston.com",
                    "Accept": "*/*",
                    "Icy-MetaData": "1",
                },
            }
        ]
    }

    dumped = yaml.safe_dump(payload, sort_keys=False)
    loaded = yaml.safe_load(dumped)

    assert loaded["stations"][0]["ffmpeg_headers"]["User-Agent"] == "Mozilla/5.0"
    assert loaded["stations"][0]["ffmpeg_headers"]["Icy-MetaData"] == "1"


def test_csv_serialization_of_header_profiles(tmp_path: Path) -> None:
    results = [
        {
            "station_id": "kbxx",
            "station_name": "KBXX",
            "market": "Houston, TX",
            "format": "Urban / Hip-Hop",
            "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/KBXXFMAAC.aac",
            "pre_header_status": "FAIL",
            "ffmpeg_status": "FAIL",
            "final_status": "FAIL",
            "tested_with_headers": True,
            "header_profile": {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://theboxhouston.com/listen-live/",
            },
            "browser_resolved": True,
            "browser_candidate_count": 1,
            "stream_type": "redirect",
            "source_platform": "radio.net / StreamTheWorld",
            "stream_stability": "unknown",
            "duration_tested_seconds": 0,
            "error_summary": "HTTP error 403 Forbidden",
            "notes": "test",
            "tested_at": "2026-06-12T00:00:00Z",
            "needs_stream_resolution": True,
        }
    ]

    validate_streams.write_outputs(results, tmp_path)
    csv_path = tmp_path / "stream_validation_results.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))

    assert rows[0]["tested_with_headers"] == "true"
    assert rows[0]["header_profile"].startswith("{")
    assert "Referer" in rows[0]["header_profile"]
