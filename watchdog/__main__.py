"""Entrypoint: python -m watchdog"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from shared.config import load_settings, load_stations
from shared.db import migrate
from shared.logging import setup_logging
from shared.metrics import start_metrics_server
from watchdog.pool import sync_station_pool
from watchdog.station_watchdog import run_health_check

DEFAULT_DB_PATH = Path("data/pipeline.db")
METRICS_PORT = 9105


def main() -> None:
    setup_logging("watchdog")
    settings = load_settings()
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(settings.db_path or DEFAULT_DB_PATH)
    migrate(db_path)
    sync_station_pool(db_path, load_stations())

    if not settings.watchdog.enabled:
        logging.getLogger(__name__).info("watchdog disabled in config")
        return

    start_metrics_server(METRICS_PORT)
    logger = logging.getLogger(__name__)
    interval = max(settings.watchdog.health_check_interval_seconds, 10)

    while True:
        try:
            summary = run_health_check(db_path, settings=settings.watchdog)
            logger.info(
                "watchdog tick",
                extra={
                    "active": summary["counts"]["active"],
                    "stale": summary["counts"]["stale"],
                    "queue_ratio": summary["queue"].drop_ratio,
                },
            )
        except Exception:
            logger.exception("watchdog tick failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
