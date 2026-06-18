#!/usr/bin/env python3
"""Investigate a radio-detected advertiser and seed trademark review records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.db import migrate
from worker.radio_hit_advertiser import (
    investigate_radio_advertiser,
    render_evidence_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Investigate radio-detected advertiser hits.")
    parser.add_argument("--db", default="data/pipeline.db", help="SQLite database path")
    parser.add_argument("--canonical-name", default="Billshappen.com")
    parser.add_argument("--normalized-name", default="billshappen")
    parser.add_argument("--vertical", default="personal_loan")
    parser.add_argument("--domain", default="billshappen.com")
    parser.add_argument("--confidence", default="high")
    parser.add_argument("--status", default="needs_review")
    parser.add_argument(
        "--stations",
        nargs="*",
        default=["klif-am-570", "ktrh-am-740", "woai-am-1200", "wsb-am-750"],
        help="Limit to specific station slugs (default: 4 reported markets)",
    )
    parser.add_argument(
        "--evidence",
        default="docs/evidence/billshappen-radio-evidence.md",
        help="Evidence markdown output path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Query only; no DB writes")
    parser.add_argument("--no-alert", action="store_true", help="Skip HIT_ADVERTISER Telegram alert")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not args.dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        applied = migrate(db_path)
        if applied:
            print(f"Applied migrations: {applied}")

    evidence_path = Path(args.evidence)
    station_names = tuple(args.stations) if args.stations else None

    try:
        result = investigate_radio_advertiser(
            db_path,
            canonical_name=args.canonical_name,
            normalized_name=args.normalized_name,
            vertical=args.vertical,
            domain=args.domain,
            source_type="radio_transcript",
            confidence=args.confidence,
            status=args.status,
            station_names=station_names,
            evidence_path=evidence_path,
            send_alert=not args.no_alert and not args.dry_run,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.dry_run:
        print(render_evidence_markdown(result))
        return 0

    summary = {
        "advertiser_entity_id": result.advertiser_entity_id,
        "trademark_entity_id": result.trademark_entity_id,
        "detections_linked": len(result.detections),
        "trademark_keywords_created": result.trademark_keywords_created,
        "trademark_keywords_existing": result.trademark_keywords_existing,
        "evidence_path": str(result.evidence_path) if result.evidence_path else None,
        "alert_sent": result.alert_sent,
        "stations": [d.station_name for d in result.detections],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
