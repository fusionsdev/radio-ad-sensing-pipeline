"""Manual import of external research candidates into the novelty engine."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.db import get_connection, retry_on_busy, transaction
from worker.novelty_engine import (
    CandidateInput,
    NoveltyConfig,
    NoveltyEvaluation,
    evaluate_candidate,
    load_novelty_config,
    process_candidate,
)

REQUIRED_FIELDS = (
    "candidate_text",
    "candidate_type",
    "vertical",
    "source_type",
    "evidence_text",
    "source_confidence",
)


@dataclass
class ImportSummary:
    total_input: int = 0
    processed: int = 0
    report_eligible: int = 0
    suppressed_known: int = 0
    suppressed_generic: int = 0
    suppressed_excluded: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_input": self.total_input,
            "processed": self.processed,
            "report_eligible": self.report_eligible,
            "suppressed_known": self.suppressed_known,
            "suppressed_generic": self.suppressed_generic,
            "suppressed_excluded": self.suppressed_excluded,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ParsedImport:
    records: list[dict[str, Any]]
    errors: list[str]


def load_candidates_json(path: Path) -> ParsedImport:
    """Load and parse a JSON array of candidate records."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ParsedImport(records=[], errors=[f"Invalid JSON: {exc}"])

    if not isinstance(raw, list):
        return ParsedImport(records=[], errors=["Input JSON must be a top-level array"])

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"Record {index}: must be an object")
            continue
        records.append(item)
    return ParsedImport(records=records, errors=errors)


def validate_record(record: dict[str, Any], *, index: int) -> list[str]:
    """Return validation error messages for one record (empty if valid)."""
    errors: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in record or record[key] in (None, ""):
            errors.append(f"Record {index}: missing required field '{key}'")
    if "source_confidence" in record and record["source_confidence"] is not None:
        try:
            confidence = float(record["source_confidence"])
            if confidence < 0.0 or confidence > 1.0:
                errors.append(f"Record {index}: source_confidence must be between 0 and 1")
        except (TypeError, ValueError):
            errors.append(f"Record {index}: source_confidence must be a number")
    candidate_text = record.get("candidate_text")
    if isinstance(candidate_text, str) and not candidate_text.strip():
        errors.append(f"Record {index}: candidate_text must not be empty")
    return errors


def record_to_candidate_input(
    record: dict[str, Any],
    *,
    raw_item_id: int | None = None,
) -> CandidateInput:
    extraction = record.get("extraction_confidence")
    return CandidateInput(
        candidate_text=str(record["candidate_text"]).strip(),
        candidate_type=str(record["candidate_type"]).strip(),
        vertical=str(record["vertical"]).strip(),
        sub_vertical=(
            str(record["sub_vertical"]).strip() if record.get("sub_vertical") else None
        ),
        source_type=str(record["source_type"]).strip(),
        source_url=str(record["source_url"]).strip() if record.get("source_url") else None,
        evidence_text=str(record["evidence_text"]).strip(),
        source_confidence=float(record["source_confidence"]),
        extraction_confidence=float(extraction) if extraction is not None else 0.0,
        raw_item_id=raw_item_id,
    )


def _classification_counts(evaluation: NoveltyEvaluation, summary: ImportSummary) -> None:
    if evaluation.report_eligible:
        summary.report_eligible += 1
    elif evaluation.novelty_status in {"known_duplicate", "near_duplicate"}:
        summary.suppressed_known += 1
    elif evaluation.novelty_status == "generic":
        summary.suppressed_generic += 1
    elif evaluation.novelty_status == "excluded_vertical":
        summary.suppressed_excluded += 1


@retry_on_busy()
def insert_raw_discovery_item(
    db_path: str | Path,
    record: dict[str, Any],
) -> int:
    """Persist one raw_discovery_items row from an import record."""
    now = time.time()
    raw_json = json.dumps(record, ensure_ascii=False)
    conn = get_connection(db_path)
    try:
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO raw_discovery_items (
                    source_type, source_url, raw_text, title, author_or_publisher,
                    published_at, market, state, raw_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record["source_type"]).strip(),
                    record.get("source_url"),
                    record.get("evidence_text") or record.get("candidate_text"),
                    record.get("title") or record.get("candidate_text"),
                    record.get("author_or_publisher"),
                    record.get("published_at"),
                    record.get("market"),
                    record.get("state"),
                    raw_json,
                    now,
                ),
            )
            return int(cursor.lastrowid)
    finally:
        conn.close()


def import_discovery_candidates(
    db_path: str | Path,
    records: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    config: NoveltyConfig | None = None,
) -> ImportSummary:
    """Validate, optionally persist, and process discovery candidate records."""
    cfg = config or load_novelty_config()
    summary = ImportSummary(total_input=len(records))

    for index, record in enumerate(records):
        field_errors = validate_record(record, index=index)
        if field_errors:
            summary.errors.extend(field_errors)
            continue

        candidate = record_to_candidate_input(record)
        try:
            if dry_run:
                evaluation = evaluate_candidate(candidate, cfg)
            else:
                raw_item_id = insert_raw_discovery_item(db_path, record)
                candidate = record_to_candidate_input(record, raw_item_id=raw_item_id)
                _, evaluation = process_candidate(db_path, candidate, config=cfg)
            summary.processed += 1
            _classification_counts(evaluation, summary)
        except Exception as exc:  # pragma: no cover - defensive for CLI
            summary.errors.append(f"Record {index}: {exc}")

    return summary


def import_discovery_candidates_file(
    db_path: str | Path,
    input_path: Path,
    *,
    dry_run: bool = False,
    config: NoveltyConfig | None = None,
) -> ImportSummary:
    """Load JSON file and import discovery candidates."""
    parsed = load_candidates_json(input_path)
    summary = ImportSummary(total_input=len(parsed.records))
    summary.errors.extend(parsed.errors)
    if parsed.errors and not parsed.records:
        return summary

    for index, record in enumerate(parsed.records):
        field_errors = validate_record(record, index=index)
        if field_errors:
            summary.errors.extend(field_errors)

    valid_records = [
        record
        for index, record in enumerate(parsed.records)
        if not validate_record(record, index=index)
    ]
    if not valid_records and parsed.records:
        summary.total_input = len(parsed.records)
        return summary

    run_summary = import_discovery_candidates(
        db_path,
        valid_records,
        dry_run=dry_run,
        config=config,
    )
    run_summary.total_input = len(parsed.records)
    run_summary.errors = summary.errors + run_summary.errors
    return run_summary
