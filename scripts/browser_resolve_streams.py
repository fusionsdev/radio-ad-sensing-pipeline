#!/usr/bin/env python3
"""Resolve public stream candidates from browser-accessible station pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover - repo already depends on PyYAML
    raise SystemExit("PyYAML is required to run this script.") from exc


MEDIA_HINT_RE = re.compile(r"(?:\.m3u8|\.mp3|\.aac|streamtheworld|triton|amperwave|/live|manifest|livestream)", re.I)
REQUEST_LINE_RE = re.compile(r"^(\d+)\.\s+\[(GET|POST|HEAD|PUT|PATCH|DELETE)\]\s+(\S+)")
HEADER_LINE_RE = re.compile(r"^([^:]+):\s*(.*)$")

PLAYWRIGHT_WRAPPER = os.environ.get(
    "PLAYWRIGHT_CLI",
    "/mnt/c/Users/Barbara/.codex/skills/playwright/scripts/playwright_cli.sh",
)


@dataclass(slots=True)
class BrowserCandidate:
    station_id: str
    page_url: str
    candidate_url: str
    source: str
    request_index: int | None = None
    request_headers: dict[str, str] | None = None


def _load_input(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        stations = data.get("stations")
        if not isinstance(stations, list):
            raise ValueError("input file must contain a stations list")
        return [row for row in stations if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    raise ValueError("input file must contain a list or a stations mapping")


def _media_like(url: str) -> bool:
    return bool(MEDIA_HINT_RE.search(url))


def _unique(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _filter_candidate_urls(urls: list[str]) -> list[str]:
    filtered: list[str] = []
    for url in urls:
        if not url.startswith("http"):
            continue
        if _media_like(url):
            filtered.append(url)
    return _unique(filtered)


def extract_candidate_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\"'\\\s>]+", text)
    return _filter_candidate_urls(urls)


def _bash(command: str) -> str:
    proc = subprocess.run(["bash", "-lc", command], capture_output=True, text=True, check=True)
    return proc.stdout


def _playwright(*args: str) -> str:
    quoted = " ".join(shlex.quote(arg) for arg in args)
    return _bash(f"{shlex.quote(PLAYWRIGHT_WRAPPER)} {quoted}")


def _open_page(url: str) -> None:
    _playwright("open", url, "--headed")


def _try_click_play() -> None:
    js = r"""() => {
      const candidates = Array.from(document.querySelectorAll('button, [role="button"], a'));
      const target = candidates.find((el) => {
        const text = `${el.textContent || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
        return /play|listen|live/.test(text);
      });
      if (!target) return null;
      target.click();
      return target.textContent || target.getAttribute('aria-label') || 'clicked';
    }"""
    try:
        _playwright("eval", js)
    except subprocess.CalledProcessError:
        return


def _capture_page_script_text() -> str:
    js = r"""() => Array.from(document.scripts).map((s) => s.textContent || '').join('\n')"""
    try:
        out = _playwright("eval", js)
    except subprocess.CalledProcessError:
        return ""
    marker = "### Result"
    if marker in out:
        out = out.split(marker, 1)[1].strip()
    return out.strip().strip('"')


def _capture_requests() -> list[tuple[int, str]]:
    out = _playwright("requests")
    requests: list[tuple[int, str]] = []
    for line in out.splitlines():
        match = REQUEST_LINE_RE.search(line.strip())
        if match:
            requests.append((int(match.group(1)), match.group(3)))
    return requests


def _capture_request_headers(index: int) -> dict[str, str]:
    out = _playwright("request-headers", str(index))
    headers: dict[str, str] = {}
    for line in out.splitlines():
        match = HEADER_LINE_RE.match(line.strip())
        if match:
            headers[match.group(1).strip()] = match.group(2).strip()
    return headers


def resolve_page(url: str) -> dict[str, Any]:
    _open_page(url)
    _try_click_play()
    script_text = _capture_page_script_text()
    page_candidates = extract_candidate_urls(script_text)
    request_candidates = _capture_requests()
    matched_requests = [
        BrowserCandidate(
            station_id=Path(urlparse(url).path).name or urlparse(url).netloc,
            page_url=url,
            candidate_url=request_url,
            source="network",
            request_index=index,
            request_headers=_capture_request_headers(index),
        )
        for index, request_url in request_candidates
        if _media_like(request_url)
    ]

    script_candidate_rows = [
        BrowserCandidate(
            station_id=Path(urlparse(url).path).name or urlparse(url).netloc,
            page_url=url,
            candidate_url=candidate_url,
            source="page-script",
        )
        for candidate_url in page_candidates
    ]

    return {
        "page_url": url,
        "browser_candidate_count": len({item.candidate_url for item in script_candidate_rows + matched_requests}),
        "candidates": [asdict(item) for item in script_candidate_rows + matched_requests],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="YAML file with station listen pages")
    parser.add_argument("--url", help="Resolve a single listen page URL")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    urls: list[str] = []
    if args.url:
        urls.append(args.url)
    elif args.input:
        rows = _load_input(args.input)
        urls = [str(row.get("url") or "").strip() for row in rows if str(row.get("url") or "").strip()]
    else:
        raise SystemExit("provide --url or --input")

    results = [resolve_page(url) for url in urls]
    payload = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
