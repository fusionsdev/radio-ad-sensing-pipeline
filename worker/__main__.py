"""Entrypoint: python -m worker"""

from __future__ import annotations

import os
import signal
import sys
import threading
from pathlib import Path

from shared.config import load_settings
from shared.db import migrate
from shared.logging import setup_logging
from shared.metrics import start_metrics_server
from worker.consumer import create_consumer

DEFAULT_DB_PATH = Path("data/pipeline.db")


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def main() -> None:
    setup_logging("worker")
    start_metrics_server(9102)
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    migrate(db_path)

    settings = load_settings()
    consumer = create_consumer(
        db_path,
        settings,
        reclaim_orphans=_env_bool("WORKER_RECLAIM_ORPHANS", True),
    )

    stop_event = threading.Event()

    def _shutdown(signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    consumer.run(stop_event)


if __name__ == "__main__":
    main()
