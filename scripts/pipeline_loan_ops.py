#!/usr/bin/env python3
"""Loan-only pipeline ops report — run inside radio-worker (live Docker DB)."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

def _project_root() -> Path:
    for candidate in (Path("/app"), Path(__file__).resolve().parent.parent):
        if (candidate / "shared").is_dir():
            return candidate
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.db import get_connection
from shared.pipeline_loan_ops import ServiceStatus, build_loan_ops_report


def _parse_services(raw: str | None) -> tuple[ServiceStatus, ...]:
    if not raw:
        return ()
    payload = json.loads(raw)
    return tuple(
        ServiceStatus(name=str(item["name"]), status=str(item["status"]), note=str(item.get("note", "")))
        for item in payload
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="/app/data/pipeline.db", help="Pipeline DB path")
    parser.add_argument(
        "--services-json",
        default=None,
        help='JSON list of {"name","status","note"} for docker services (from host wrapper)',
    )
    parser.add_argument(
        "--services-b64",
        default=None,
        help="Base64-encoded services JSON (preferred from PowerShell wrapper)",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 1

    raw_services = args.services_json
    if args.services_b64:
        raw_services = base64.b64decode(args.services_b64.encode("ascii")).decode("utf-8")
    services = _parse_services(raw_services)
    conn = get_connection(str(db_path))
    try:
        report = build_loan_ops_report(conn, db_path=str(db_path), services=services)
    finally:
        conn.close()

    print(report.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
