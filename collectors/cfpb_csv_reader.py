"""Stream CFPB bulk complaint CSV with in-memory-safe filtering."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from collectors.cfpb_api_client import parse_complaint_record


def _row_matches_filters(
    row: dict[str, str],
    *,
    target_states: set[str],
    target_products: set[str],
    date_from: str | None,
    date_to: str | None,
) -> bool:
    state = (row.get("state") or "").strip().upper()
    if target_states and state not in target_states:
        return False
    product = (row.get("product") or "").strip()
    if target_products and product not in target_products:
        return False
    date_received = (row.get("date_received") or "").strip()
    if date_from and date_received and date_received < date_from:
        return False
    if date_to and date_received and date_received > date_to:
        return False
    return True


def _csv_row_to_record(row: dict[str, str]) -> dict[str, object]:
    source = dict(row)
    record = parse_complaint_record(source)
    record["raw_json"] = json.dumps(source)
    return record


def stream_complaints_csv(
    csv_path: Path,
    *,
    target_states: list[str],
    target_products: list[str],
    date_from: str | None = None,
    date_to: str | None = None,
    max_records: int = 50000,
    resume_after_complaint_id: str | None = None,
) -> Iterator[dict[str, object]]:
    """Stream-filter a CFPB bulk CSV without loading the full file."""
    states = {s.strip().upper() for s in target_states}
    products = {p.strip() for p in target_products}
    seen = 0
    skipping = bool(resume_after_complaint_id)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            complaint_id = (row.get("complaint_id") or "").strip()
            if skipping:
                if complaint_id == resume_after_complaint_id:
                    skipping = False
                continue
            if not _row_matches_filters(
                row,
                target_states=states,
                target_products=products,
                date_from=date_from,
                date_to=date_to,
            ):
                continue
            record = _csv_row_to_record(row)
            if record.get("complaint_id"):
                yield record
                seen += 1
                if seen >= max_records:
                    return
