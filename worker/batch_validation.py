"""Batch validation workflow for curated research candidate imports."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from worker.discovery_import import (
    ImportSummary,
    insert_raw_discovery_item,
    load_candidates_json,
    record_to_candidate_input,
    validate_record,
)
from worker.novelty_engine import (
    NoveltyConfig,
    NoveltyEvaluation,
    evaluate_candidate,
    load_novelty_config,
    process_candidate,
)

SCORE_BUCKET_LABELS = ("0-20", "21-40", "41-60", "61-80", "81-100")


@dataclass(frozen=True)
class BatchCandidateResult:
    index: int
    candidate_text: str
    candidate_type: str
    vertical: str | None
    sub_vertical: str | None
    source_type: str
    source_url: str | None
    novelty_status: str
    novelty_score: float
    opportunity_score: float
    report_eligible: bool
    report_suppressed_reason: str | None
    known_match: str | None
    reason: str


@dataclass
class BatchValidationReport:
    batch_id: str
    input_path: Path
    summary: ImportSummary
    status_counts: dict[str, int] = field(default_factory=dict)
    suppression_counts: dict[str, int] = field(default_factory=dict)
    score_distribution: dict[str, int] = field(default_factory=dict)
    records: list[BatchCandidateResult] = field(default_factory=list)

    @property
    def top_opportunities(self) -> list[BatchCandidateResult]:
        eligible = [row for row in self.records if row.report_eligible]
        return sorted(
            eligible,
            key=lambda row: (row.opportunity_score, row.novelty_score),
            reverse=True,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "input_path": str(self.input_path),
            "summary": self.summary.as_dict(),
            "status_counts": dict(self.status_counts),
            "suppression_counts": dict(self.suppression_counts),
            "score_distribution": dict(self.score_distribution),
            "top_opportunities": [
                {
                    "candidate_text": row.candidate_text,
                    "novelty_score": row.novelty_score,
                    "opportunity_score": row.opportunity_score,
                    "vertical": row.vertical,
                }
                for row in self.top_opportunities[:10]
            ],
        }


def _score_bucket(score: float) -> str:
    if score <= 20:
        return "0-20"
    if score <= 40:
        return "21-40"
    if score <= 60:
        return "41-60"
    if score <= 80:
        return "61-80"
    return "81-100"


def _evaluation_to_result(
    *,
    index: int,
    record: dict[str, Any],
    evaluation: NoveltyEvaluation,
) -> BatchCandidateResult:
    return BatchCandidateResult(
        index=index,
        candidate_text=str(record["candidate_text"]).strip(),
        candidate_type=str(record["candidate_type"]).strip(),
        vertical=str(record.get("vertical") or "").strip() or None,
        sub_vertical=str(record.get("sub_vertical") or "").strip() or None,
        source_type=str(record["source_type"]).strip(),
        source_url=str(record["source_url"]).strip() if record.get("source_url") else None,
        novelty_status=evaluation.novelty_status,
        novelty_score=evaluation.novelty_score,
        opportunity_score=evaluation.opportunity_score,
        report_eligible=evaluation.report_eligible,
        report_suppressed_reason=evaluation.report_suppressed_reason,
        known_match=evaluation.known_match,
        reason=evaluation.reason,
    )


def _finalize_report(
    *,
    batch_id: str,
    input_path: Path,
    summary: ImportSummary,
    records: list[BatchCandidateResult],
) -> BatchValidationReport:
    status_counts = Counter(row.novelty_status for row in records)
    suppression_counts = Counter(
        row.report_suppressed_reason
        for row in records
        if row.report_suppressed_reason and not row.report_eligible
    )
    score_distribution = Counter(_score_bucket(row.novelty_score) for row in records)
    return BatchValidationReport(
        batch_id=batch_id,
        input_path=input_path,
        summary=summary,
        status_counts=dict(sorted(status_counts.items())),
        suppression_counts=dict(sorted(suppression_counts.items())),
        score_distribution={label: score_distribution.get(label, 0) for label in SCORE_BUCKET_LABELS},
        records=records,
    )


def tag_records_with_batch_id(
    records: list[dict[str, Any]],
    batch_id: str,
) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for record in records:
        copy = dict(record)
        copy.setdefault("batch_id", batch_id)
        tagged.append(copy)
    return tagged


def run_batch_validation(
    db_path: str | Path,
    input_path: Path,
    *,
    batch_id: str | None = None,
    dry_run: bool = False,
    config: NoveltyConfig | None = None,
) -> BatchValidationReport:
    """Import or dry-run evaluate a research batch and build a validation report."""
    cfg = config or load_novelty_config()
    parsed = load_candidates_json(input_path)
    resolved_batch_id = batch_id or input_path.stem.replace(".sample", "")
    summary = ImportSummary(total_input=len(parsed.records))
    summary.errors.extend(parsed.errors)
    records_out: list[BatchCandidateResult] = []

    if parsed.errors and not parsed.records:
        return _finalize_report(
            batch_id=resolved_batch_id,
            input_path=input_path,
            summary=summary,
            records=records_out,
        )

    tagged_records = tag_records_with_batch_id(parsed.records, resolved_batch_id)

    for index, record in enumerate(tagged_records):
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
            if evaluation.report_eligible:
                summary.report_eligible += 1
            elif evaluation.novelty_status in {"known_duplicate", "near_duplicate"}:
                summary.suppressed_known += 1
            elif evaluation.novelty_status == "generic":
                summary.suppressed_generic += 1
            elif evaluation.novelty_status == "excluded_vertical":
                summary.suppressed_excluded += 1
            records_out.append(
                _evaluation_to_result(index=index, record=record, evaluation=evaluation)
            )
        except Exception as exc:  # pragma: no cover
            summary.errors.append(f"Record {index}: {exc}")

    summary.total_input = len(parsed.records)
    return _finalize_report(
        batch_id=resolved_batch_id,
        input_path=input_path,
        summary=summary,
        records=records_out,
    )


def write_batch_csv(report: BatchValidationReport, output_path: Path) -> Path:
    """Write per-candidate batch validation results to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "batch_id",
        "index",
        "candidate_text",
        "candidate_type",
        "vertical",
        "sub_vertical",
        "source_type",
        "source_url",
        "novelty_status",
        "novelty_score",
        "opportunity_score",
        "report_eligible",
        "report_suppressed_reason",
        "known_match",
        "reason",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report.records:
            writer.writerow(
                {
                    "batch_id": report.batch_id,
                    "index": row.index,
                    "candidate_text": row.candidate_text,
                    "candidate_type": row.candidate_type,
                    "vertical": row.vertical or "",
                    "sub_vertical": row.sub_vertical or "",
                    "source_type": row.source_type,
                    "source_url": row.source_url or "",
                    "novelty_status": row.novelty_status,
                    "novelty_score": f"{row.novelty_score:.2f}",
                    "opportunity_score": f"{row.opportunity_score:.2f}",
                    "report_eligible": "yes" if row.report_eligible else "no",
                    "report_suppressed_reason": row.report_suppressed_reason or "",
                    "known_match": row.known_match or "",
                    "reason": row.reason,
                }
            )
    return output_path


def write_batch_meta(report: BatchValidationReport, output_path: Path) -> Path:
    """Write batch summary metadata JSON for dashboard/CLI review."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return output_path


def format_batch_summary(report: BatchValidationReport) -> str:
    """Human-readable batch validation summary for CLI output."""
    lines = [
        f"=== Research batch validation: {report.batch_id} ===",
        f"Input: {report.input_path}",
        f"Total input:        {report.summary.total_input}",
        f"Processed:          {report.summary.processed}",
        f"Report eligible:    {report.summary.report_eligible}",
        f"Suppressed known:   {report.summary.suppressed_known}",
        f"Suppressed generic: {report.summary.suppressed_generic}",
        f"Suppressed excluded:{report.summary.suppressed_excluded}",
        f"Errors:             {len(report.summary.errors)}",
        "",
        "Novelty status counts:",
    ]
    for status, count in sorted(report.status_counts.items()):
        lines.append(f"  {status}: {count}")

    lines.extend(["", "Suppressed reasons:"])
    if report.suppression_counts:
        for reason, count in sorted(report.suppression_counts.items()):
            lines.append(f"  {reason}: {count}")
    else:
        lines.append("  (none)")

    lines.extend(["", "Novelty score distribution:"])
    for bucket, count in report.score_distribution.items():
        lines.append(f"  {bucket}: {count}")

    lines.extend(["", "Top opportunities:"])
    if report.top_opportunities:
        for row in report.top_opportunities[:10]:
            lines.append(
                f"  - {row.candidate_text} "
                f"(novelty={row.novelty_score:.0f}, opp={row.opportunity_score:.0f}, "
                f"vertical={row.vertical or 'n/a'})"
            )
    else:
        lines.append("  (none)")

    if report.summary.errors:
        lines.extend(["", "Errors:"])
        for error in report.summary.errors:
            lines.append(f"  - {error}")

    return "\n".join(lines)
