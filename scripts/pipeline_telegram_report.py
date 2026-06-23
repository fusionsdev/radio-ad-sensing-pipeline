#!/usr/bin/env python3
"""Send a pipeline + keyword status report to Telegram (one-shot)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alerter.service import TelegramBotApi
from shared.config import load_settings, load_telegram_settings
from shared.db import get_connection
from shared.pipeline_report import build_pipeline_report_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/pipeline.db")
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help="Lookback window (default: settings.alerter_periodic_report_hours)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print message only")
    args = parser.parse_args(argv)

    settings = load_settings()
    interval = args.hours if args.hours is not None else settings.alerter_periodic_report_hours
    now_ts = time.time()
    since_ts = now_ts - (interval * 3600)

    conn = get_connection(args.db)
    try:
        snapshot = build_pipeline_report_snapshot(
            conn,
            now_ts=now_ts,
            since_ts=since_ts,
            interval_hours=interval,
        )
    finally:
        conn.close()

    message = snapshot.format_telegram()
    if args.dry_run:
        print(message)
        return 0

    telegram = load_telegram_settings()
    token = telegram.telegram_bot_token
    chat_id = telegram.telegram_chat_id
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required", file=sys.stderr)
        print(message)
        return 1

    client = TelegramBotApi(token)
    try:
        client.send_message(chat_id, message)
    finally:
        client.close()
    print("sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
