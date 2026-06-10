"""CFPB complaint search API client with pagination and retry."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)

CFPB_API_BASE = (
    "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
)


def _build_url(params: dict[str, str | int]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return f"{CFPB_API_BASE}?{query}"


def _fetch_page(url: str, *, max_retries: int = 5) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            logger.info("CFPB API request: %s", url)
            with urllib.request.urlopen(url, timeout=60) as response:
                status = response.status
                logger.info("CFPB API response status: %s", status)
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {429, 500, 502, 503, 504} and attempt < max_retries - 1:
                delay = 0.5 * (2**attempt)
                logger.warning("CFPB API HTTP %s — retry in %.1fs", exc.code, delay)
                time.sleep(delay)
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = 0.5 * (2**attempt)
                logger.warning("CFPB API URL error — retry in %.1fs: %s", delay, exc)
                time.sleep(delay)
                continue
            raise
    raise last_error  # pragma: no cover


def parse_complaint_record(source: dict[str, Any]) -> dict[str, Any]:
    """Map CFPB API _source document to flat complaint dict."""
    return {
        "complaint_id": str(source.get("complaint_id", "")),
        "date_received": source.get("date_received"),
        "product": source.get("product"),
        "sub_product": source.get("sub_product"),
        "issue": source.get("issue"),
        "sub_issue": source.get("sub_issue"),
        "consumer_complaint_narrative": source.get("consumer_complaint_narrative"),
        "company_public_response": source.get("company_public_response"),
        "company": source.get("company"),
        "state": source.get("state"),
        "zip_code": source.get("zip_code"),
        "tags": source.get("tags"),
        "consumer_consent_provided": source.get("consumer_consent_provided"),
        "submitted_via": source.get("submitted_via"),
        "date_sent_to_company": source.get("date_sent_to_company"),
        "company_response_to_consumer": source.get("company_response_to_consumer"),
        "timely_response": source.get("timely_response"),
        "consumer_disputed": source.get("consumer_disputed"),
        "raw_json": json.dumps(source),
    }


def fetch_complaints(
    *,
    state: str | None = None,
    product: str | None = None,
    date_received_min: str | None = None,
    date_received_max: str | None = None,
    page_size: int = 100,
    max_records: int = 50000,
    rate_limit_sleep: float = 0.5,
    has_narrative: bool | None = None,
) -> Iterator[dict[str, Any]]:
    """Paginate CFPB complaint API and yield parsed complaint records."""
    fetched = 0
    offset = 0
    while fetched < max_records:
        size = min(page_size, max_records - fetched)
        params: dict[str, str | int] = {
            "size": size,
            "from": offset,
        }
        if state:
            params["state"] = state
        if product:
            params["product"] = product
        if date_received_min:
            params["date_received_min"] = date_received_min
        if date_received_max:
            params["date_received_max"] = date_received_max
        if has_narrative is not None:
            params["has_narrative"] = "true" if has_narrative else "false"

        url = _build_url(params)
        payload = _fetch_page(url)
        hits = payload.get("hits", {}).get("hits", [])
        if not hits:
            break
        for hit in hits:
            source = hit.get("_source", hit)
            record = parse_complaint_record(source)
            if record.get("complaint_id"):
                yield record
                fetched += 1
                if fetched >= max_records:
                    return
        offset += len(hits)
        if rate_limit_sleep > 0:
            time.sleep(rate_limit_sleep)
