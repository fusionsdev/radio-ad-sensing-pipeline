"""Entrypoint: python -m alerter."""

from __future__ import annotations

import signal
import sys
import threading
from pathlib import Path

from alerter.service import AlerterService
from shared.config import load_settings
from shared.logging import setup_logging
from shared.metrics import start_metrics_server


def main() -> None:
    log = setup_logging("alerter")
    start_metrics_server(9103)
    settings = load_settings()
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(settings.db_path)
    service = AlerterService(db_path=db_path, settings=settings, logger=log)

    stop_event = threading.Event()

    def _shutdown(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    service.run(stop_event)


if __name__ == "__main__":
    main()
