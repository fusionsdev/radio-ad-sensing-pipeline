"""WP-4 LLM extraction prompt, Ollama client, and phone normalization."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Protocol

from pydantic import ValidationError

from shared.models import AdExtraction

DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")


class OllamaHTTPClient(Protocol):
    """Small protocol for tests and the urllib-backed production client."""

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class UrllibOllamaHTTPClient:
    """Minimal /api/generate client to avoid pulling HTTP dependencies into worker core."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_BASE_URL, *, timeout_sec: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:  # noqa: S310 - local Ollama endpoint
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:  # pragma: no cover - network failure shape
            raise RuntimeError(f"Ollama generate request failed: {exc}") from exc
        return json.loads(raw)


def extraction_json_schema() -> dict[str, Any]:
    """Return a strict JSON schema containing only fields the LLM is allowed to emit."""
    schema = AdExtraction.model_json_schema()
    schema["additionalProperties"] = False
    # Ollama structured output is more reliable when title/description noise is removed.
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        if isinstance(prop, dict):
            prop.pop("title", None)
    return schema


def build_extraction_prompt(transcript_text: str) -> str:
    """Build the extraction instruction with few-shot ad and non-ad cues."""
    return f"""
You are extracting paid advertisement signals from ASR text for U.S. news/talk radio.
Return ONLY JSON that conforms to the provided schema. Do not include markdown.

Decision rules:
- is_ad=true only for a paid spot, sponsorship read, or direct response advertisement.
- Strong ad-signal cues: call to action, phone number, URL, "sponsored", "paid for", limited-time offer,
  financing/funding promises, free quote/consultation, repeated brand + contact instructions.
- is_ad=false for news interviews, host discussion, market commentary, public affairs, or generic talk about loans
  without a direct commercial offer.
- ad_category should be concise, e.g. business_funding, debt_relief, mortgage_refinance, tax_relief, insurance.
- company_name, phone_number, website, offer_summary, and key_claims must be null/empty when unknown.
- confidence is 0.0-1.0. Use lower confidence for ambiguous host reads or incomplete chunk-boundary text.
- Normalize claims into short factual phrases. Do not invent missing details.

Few-shot examples:
1) Transcript: "This hour is sponsored by Rapid Capital. Need cash for payroll? Call 800-555-1212 now for same-day funding."
   JSON: {{"is_ad": true, "ad_category": "business_funding", "company_name": "Rapid Capital", "phone_number": "800-555-1212", "website": null, "offer_summary": "same-day business funding", "key_claims": ["cash for payroll", "same-day funding"], "confidence": 0.94}}
2) Transcript: "The senator discussed small-business lending standards and today's interest-rate outlook."
   JSON: {{"is_ad": false, "ad_category": null, "company_name": null, "phone_number": null, "website": null, "offer_summary": null, "key_claims": [], "confidence": 0.86}}
3) Transcript: "Tax debt? The Tax Relief Center can stop wage garnishments. Visit taxhelp.example or call one eight hundred tax help."
   JSON: {{"is_ad": true, "ad_category": "tax_relief", "company_name": "The Tax Relief Center", "phone_number": "8008294357", "website": "taxhelp.example", "offer_summary": "tax debt relief", "key_claims": ["stop wage garnishments"], "confidence": 0.91}}

Transcript to classify:
<<<TRANSCRIPT
{transcript_text.strip()}
TRANSCRIPT
>>>""".strip()


_PHONE_WORDS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
_KEYPAD = {
    **dict.fromkeys("ABC", "2"),
    **dict.fromkeys("DEF", "3"),
    **dict.fromkeys("GHI", "4"),
    **dict.fromkeys("JKL", "5"),
    **dict.fromkeys("MNO", "6"),
    **dict.fromkeys("PQRS", "7"),
    **dict.fromkeys("TUV", "8"),
    **dict.fromkeys("WXYZ", "9"),
}
_TOLL_FREE_PREFIXES = frozenset({"800", "888", "877", "866", "855", "844", "833"})


def _toll_free_prefix(digits: str) -> str | None:
    """Return the toll-free area code when *digits* begins with one, else None."""
    if len(digits) >= 4 and digits.startswith("1"):
        prefix = digits[1:4]
    elif len(digits) >= 3:
        prefix = digits[:3]
    else:
        return None
    return prefix if prefix in _TOLL_FREE_PREFIXES else None


def _accept_spelled_digits(digits: str) -> bool:
    return len(digits) >= 7 or _toll_free_prefix(digits) is not None


def _has_explicit_digits_or_vanity(raw: str) -> bool:
    """True when vanity/digit parsing is appropriate (not prose-only spelled words)."""
    if re.search(r"\d", raw):
        return True
    compact = re.sub(r"[\s\-().]", "", raw.upper())
    return bool(re.search(r"\d", compact) and re.search(r"[A-Z]", compact))


def _parse_spelled_phone(text: str) -> str | None:
    tokens = re.findall(r"[a-z]+", text.lower())
    best = ""
    current: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in _PHONE_WORDS:
            digit = _PHONE_WORDS[token]
            if i + 1 < len(tokens) and tokens[i + 1] == "hundred":
                current.extend([digit, "0", "0"])
                i += 2
                continue
            current.append(digit)
        elif token == "hundred" and current:
            # Already handled by the previous digit. Treat a stray "hundred" as a separator.
            pass
        else:
            if len(current) > len(best):
                best = "".join(current)
            current = []
        i += 1
    if len(current) > len(best):
        best = "".join(current)
    return best if _accept_spelled_digits(best) else None


def _parse_digits_and_vanity(raw: str) -> str | None:
    upper = raw.upper()
    chars: list[str] = []
    for char in upper:
        if char.isdigit():
            chars.append(char)
        elif char in _KEYPAD:
            chars.append(_KEYPAD[char])
    digits = "".join(chars)
    return digits if len(digits) >= 7 else None


def normalize_phone_number(raw: str | None) -> str | None:
    """Normalize digit, spelled-out, and vanity phone strings to digits only.

    Literal digits / vanity letters take precedence over spelled-out parsing so a
    real number like ``800-555-1212`` is never overridden by stray number-words
    in surrounding prose (``one``/``oh``/``o``), which could otherwise fabricate a
    bogus phone and cause two unrelated ads to merge on phone equality.
    """
    if not raw:
        return None
    if _has_explicit_digits_or_vanity(raw):
        digits = _parse_digits_and_vanity(raw)
        if digits:
            return digits
    return _parse_spelled_phone(raw)


def _load_response_json(raw_response: Any) -> dict[str, Any]:
    if isinstance(raw_response, dict):
        return raw_response
    if not isinstance(raw_response, str):
        raise ValueError("Ollama response is not a JSON string")
    text = raw_response.strip()
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise
        loaded = json.loads(match.group(0))
    if not isinstance(loaded, dict):
        raise ValueError("Ollama response JSON must be an object")
    return loaded


class OllamaExtractor:
    """Structured-output extractor with one retry for invalid JSON/schema output."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        http_client: OllamaHTTPClient | None = None,
        max_invalid_retries: int = 1,
    ) -> None:
        self.model = model
        self.http_client = http_client or UrllibOllamaHTTPClient()
        self.max_invalid_retries = max_invalid_retries

    def extract(self, transcript_text: str) -> AdExtraction:
        last_error: Exception | None = None
        for attempt in range(self.max_invalid_retries + 1):
            prompt = build_extraction_prompt(transcript_text)
            if attempt:
                prompt += "\n\nPrevious response was invalid. Return only a complete JSON object matching the schema."
            payload = {
                "model": self.model,
                "prompt": prompt,
                "format": extraction_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            }
            try:
                response = self.http_client.generate(payload)
                data = _load_response_json(response.get("response"))
                extraction = AdExtraction.model_validate(data)
                phone_norm = normalize_phone_number(extraction.phone_number)
                if phone_norm != extraction.phone_number:
                    extraction = extraction.model_copy(update={"phone_number": phone_norm})
                return extraction
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError) as exc:
                last_error = exc
                continue
        raise ValueError(f"invalid LLM extraction response after retry: {last_error}") from last_error
