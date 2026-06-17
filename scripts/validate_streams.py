#!/usr/bin/env python3
"""Validate radio stream candidates with ffmpeg and write summary artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover - repo already depends on PyYAML
    raise SystemExit("PyYAML is required to run this script.") from exc


OPENING_RE = re.compile(r"Opening '([^']+)' for reading")
HTTP_ERROR_RE = re.compile(r"HTTP error (\d{3})")
STATUS_RE = re.compile(r"Server returned 5XX Server Error reply")

HEADER_ORDER = ("User-Agent", "Referer", "Origin", "Accept", "Icy-MetaData")
TOKENISH_KEYS = {"token", "auth", "signature", "sig", "expires", "exp", "st", "se", "sp", "sv"}


@dataclass(slots=True)
class StreamCandidate:
    station_id: str
    station_name: str
    market: str
    format: str
    url: str
    raw: dict[str, Any] = field(default_factory=dict)
    ffmpeg_headers: dict[str, str] = field(default_factory=dict)
    browser_resolved: bool = False
    browser_candidate_count: int = 0


def _load_input(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _normalize_header_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered == "user-agent":
        return "User-Agent"
    if lowered == "icy-metadata":
        return "Icy-MetaData"
    return "-".join(part.capitalize() for part in lowered.split("-"))


def _normalize_headers(raw_headers: Any) -> dict[str, str]:
    if not raw_headers:
        return {}
    if not isinstance(raw_headers, Mapping):
        raise ValueError("headers must be a mapping")

    headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        if value is None:
            continue
        normalized_key = _normalize_header_name(str(key))
        text = str(value).strip()
        if text:
            headers[normalized_key] = text
    return headers


def _collect_header_profile(raw: Mapping[str, Any], defaults: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = _normalize_headers(raw.get("ffmpeg_headers") or raw.get("headers") or raw.get("header_profile"))
    if defaults:
        for key, value in defaults.items():
            if value:
                headers[_normalize_header_name(key)] = value
    return headers


def _normalize_candidates(
    data: Any,
    *,
    default_headers: Mapping[str, str] | None = None,
) -> list[StreamCandidate]:
    if isinstance(data, dict):
        if isinstance(data.get("stations"), list):
            data = data["stations"]
        elif isinstance(data.get("candidates"), list):
            data = data["candidates"]
        else:
            raise ValueError("input file must contain a top-level list or a stations/candidates list")

    if not isinstance(data, list):
        raise ValueError("input file must contain a list of station candidates")

    candidates: list[StreamCandidate] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        station_id = str(raw.get("station_id") or raw.get("id") or raw.get("name") or "").strip()
        station_name = str(raw.get("station_name") or raw.get("name") or raw.get("display_name") or station_id).strip()
        market = str(raw.get("market") or "").strip()
        fmt = str(raw.get("format") or "").strip()
        candidates.append(
            StreamCandidate(
                station_id=station_id or station_name,
                station_name=station_name or station_id,
                market=market,
                format=fmt,
                url=url,
                raw=dict(raw),
                ffmpeg_headers=_collect_header_profile(raw, defaults=default_headers),
                browser_resolved=bool(raw.get("browser_resolved", False)),
                browser_candidate_count=int(raw.get("browser_candidate_count") or 0),
            )
        )
    return candidates


def _infer_stream_type(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if "livestream-redirect" in path:
        return "redirect"
    if "/direct/" in path:
        return "direct"
    if path.endswith(".m3u8"):
        return "m3u8"
    if path.endswith(".pls"):
        return "pls"
    if path.endswith(".mp3"):
        return "mp3"
    if path.endswith(".aac") or path.endswith(".m4a"):
        return "aac"
    return "listen-page"


def _looks_tokenized(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.query:
        return False
    query_keys = {key.lower() for key in parse_qs(parsed.query)}
    return bool(query_keys & TOKENISH_KEYS)


def _build_header_args(headers: Mapping[str, str] | None) -> list[str]:
    if not headers:
        return []
    args: list[str] = []
    user_agent = headers.get("User-Agent")
    if user_agent:
        args.extend(["-user_agent", user_agent])
    header_lines: list[str] = []
    for key in HEADER_ORDER[1:]:
        value = headers.get(key)
        if value:
            header_lines.append(f"{key}: {value}")
    if header_lines:
        args.extend(["-headers", "\r\n".join(header_lines) + "\r\n"])
    return args


def build_ffmpeg_command(
    url: str,
    duration_seconds: int,
    *,
    headers: Mapping[str, str] | None = None,
) -> list[str]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
    ]
    cmd.extend(_build_header_args(headers))
    cmd.extend(
        [
            "-i",
            url,
            "-t",
            str(duration_seconds),
            "-f",
            "null",
            "-",
        ]
    )
    return cmd


def _run_ffmpeg(
    url: str,
    duration_seconds: int,
    timeout_seconds: int,
    *,
    headers: Mapping[str, str] | None = None,
) -> tuple[int, str, list[str]]:
    cmd = build_ffmpeg_command(url, duration_seconds, headers=headers)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    stderr = proc.stderr or ""
    opened_urls = OPENING_RE.findall(stderr)
    return proc.returncode, stderr, opened_urls


def _classify_status(
    returncode: int,
    stderr: str,
    input_url: str,
    opened_urls: list[str],
) -> str:
    if returncode != 0:
        if _looks_tokenized(input_url) or "403 Forbidden" in stderr or HTTP_ERROR_RE.search(stderr) or STATUS_RE.search(stderr):
            return "FAIL"
        return "FAIL"

    if _looks_tokenized(input_url):
        return "TOKENIZED"

    if opened_urls:
        normalized_input = input_url.rstrip("/")
        normalized_opened = [u.rstrip("/") for u in opened_urls]
        if any(url != normalized_input for url in normalized_opened):
            return "REDIRECT"

    return "PASS"


def _summarize_error(stderr: str) -> str:
    text = stderr.strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:4])[:500]


def _status_to_stability(status: str) -> str:
    return {
        "PASS": "stable",
        "REDIRECT": "redirect",
        "HEADER_REQUIRED": "header_required",
        "TOKENIZED": "tokenized",
        "FAIL": "unknown",
        "UNKNOWN": "unknown",
    }.get(status, "unknown")


def validate_candidate(
    candidate: StreamCandidate,
    duration_seconds: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    tested_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    stream_type = _infer_stream_type(candidate.url)

    result: dict[str, Any] = dict(candidate.raw)
    result.update(
        {
            "station_id": candidate.station_id,
            "station_name": candidate.station_name,
            "market": candidate.market,
            "format": candidate.format,
            "url": candidate.url,
            "stream_type": stream_type,
            "browser_resolved": candidate.browser_resolved,
            "browser_candidate_count": candidate.browser_candidate_count,
            "tested_with_headers": bool(candidate.ffmpeg_headers),
            "header_profile": candidate.ffmpeg_headers or {},
            "pre_header_status": "UNKNOWN",
            "pre_header_error_summary": "",
            "ffmpeg_status": "UNKNOWN",
            "final_status": "UNKNOWN",
            "duration_tested_seconds": 0,
            "error_summary": "",
            "tested_at": tested_at,
        }
    )

    if stream_type == "listen-page":
        return result

    try:
        returncode, stderr, opened_urls = _run_ffmpeg(candidate.url, duration_seconds, timeout_seconds)
        pre_status = _classify_status(returncode, stderr, candidate.url, opened_urls)
        pre_error = _summarize_error(stderr)
        result["pre_header_status"] = pre_status
        result["pre_header_error_summary"] = pre_error

        final_status = pre_status
        final_error = pre_error
        final_headers_used = False
        final_opened_urls = opened_urls

        if pre_status == "FAIL" and candidate.ffmpeg_headers:
            headers = candidate.ffmpeg_headers
            final_headers_used = True
            header_returncode, header_stderr, header_opened_urls = _run_ffmpeg(
                candidate.url,
                duration_seconds,
                timeout_seconds,
                headers=headers,
            )
            header_status = _classify_status(header_returncode, header_stderr, candidate.url, header_opened_urls)
            header_error = _summarize_error(header_stderr)
            result["header_attempt_status"] = header_status
            result["header_attempt_error_summary"] = header_error
            result["tested_with_headers"] = True
            result["header_profile"] = headers
            if header_status in {"PASS", "REDIRECT"}:
                final_status = "HEADER_REQUIRED"
                final_error = header_error
                final_opened_urls = header_opened_urls
            elif header_status == "TOKENIZED" or _looks_tokenized(candidate.url):
                final_status = "TOKENIZED"
                final_error = header_error or pre_error
                final_opened_urls = header_opened_urls
            else:
                final_status = "FAIL"
                final_error = header_error or pre_error
        elif pre_status == "TOKENIZED":
            final_status = "TOKENIZED"
        elif pre_status == "FAIL":
            final_status = "FAIL"

        duration_tested = duration_seconds if final_status in {"PASS", "REDIRECT", "TOKENIZED", "HEADER_REQUIRED"} else 0
        result.update(
            {
                "ffmpeg_status": final_status,
                "final_status": final_status,
                "duration_tested_seconds": duration_tested,
                "error_summary": final_error,
                "stream_stability": _status_to_stability(final_status),
            }
        )

        if final_headers_used and "header_attempt_status" not in result:
            result["header_attempt_status"] = final_status
        if final_headers_used and "header_attempt_error_summary" not in result:
            result["header_attempt_error_summary"] = final_error

        return result
    except subprocess.TimeoutExpired as exc:
        stderr = ""
        if exc.stderr:
            stderr = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", errors="replace")
        result.update(
            {
                "ffmpeg_status": "FAIL",
                "final_status": "FAIL",
                "duration_tested_seconds": 0,
                "error_summary": f"timeout after {timeout_seconds}s" + (f" | {_summarize_error(stderr)}" if stderr else ""),
                "stream_stability": "unknown",
            }
        )
        return result


def write_outputs(results: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "stream_validation_results.json"
    csv_path = output_dir / "stream_validation_results.csv"

    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    preferred_fieldnames = [
        "station_id",
        "station_name",
        "market",
        "format",
        "url",
        "pre_header_status",
        "ffmpeg_status",
        "final_status",
        "tested_with_headers",
        "header_profile",
        "browser_resolved",
        "browser_candidate_count",
        "stream_type",
        "source_platform",
        "stream_stability",
        "duration_tested_seconds",
        "error_summary",
        "pre_header_error_summary",
        "header_attempt_status",
        "header_attempt_error_summary",
        "notes",
        "tested_at",
        "needs_stream_resolution",
    ]
    fieldnames: list[str] = []
    seen: set[str] = set()
    for name in preferred_fieldnames:
        if any(name in row for row in results):
            fieldnames.append(name)
            seen.add(name)
    for row in results:
        for name in row:
            if name not in seen:
                fieldnames.append(name)
                seen.add(name)

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({name: _stringify_csv_value(row.get(name, "")) for name in fieldnames})


def _stringify_csv_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="YAML or JSON file containing station candidates")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Directory for JSON and CSV outputs")
    parser.add_argument("--duration", type=int, default=10, help="Seconds of audio to test per stream")
    parser.add_argument("--timeout", type=int, default=30, help="Maximum seconds to wait for each ffmpeg run")
    parser.add_argument("--user-agent", dest="user_agent", default=None, help="Optional ffmpeg User-Agent header")
    parser.add_argument("--referer", dest="referer", default=None, help="Optional ffmpeg Referer header")
    parser.add_argument("--origin", dest="origin", default=None, help="Optional ffmpeg Origin header")
    parser.add_argument("--accept", dest="accept", default=None, help="Optional ffmpeg Accept header")
    parser.add_argument(
        "--icy-metadata",
        dest="icy_metadata",
        action="store_true",
        help="Send Icy-MetaData: 1 with ffmpeg requests",
    )
    return parser.parse_args(argv)


def _default_headers_from_args(args: argparse.Namespace) -> dict[str, str]:
    headers: dict[str, str] = {}
    if args.user_agent:
        headers["User-Agent"] = args.user_agent
    if args.referer:
        headers["Referer"] = args.referer
    if args.origin:
        headers["Origin"] = args.origin
    if args.accept:
        headers["Accept"] = args.accept
    if args.icy_metadata:
        headers["Icy-MetaData"] = "1"
    return headers


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    default_headers = _default_headers_from_args(args)
    data = _load_input(args.input)
    candidates = _normalize_candidates(data, default_headers=default_headers)
    results = [validate_candidate(candidate, args.duration, args.timeout) for candidate in candidates]
    write_outputs(results, args.output_dir)
    print(f"Validated {len(results)} stream candidate(s).")
    print(f"Wrote {args.output_dir / 'stream_validation_results.json'}")
    print(f"Wrote {args.output_dir / 'stream_validation_results.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
