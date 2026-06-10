"""Entrypoint: python -m ingestor"""

from __future__ import annotations

import signal
import sys
import threading
from pathlib import Path

from ingestor.repository import upsert_station
from ingestor.supervisor import create_station_ingestors
from shared.config import load_settings, load_stations
from shared.db import migrate
from shared.logging import setup_logging
from shared.metrics import start_metrics_server

DEFAULT_DB_PATH = Path("data/pipeline.db")


def main() -> None:
    setup_logging("ingestor")
    start_metrics_server(9101)
    settings = load_settings()
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(settings.db_path or DEFAULT_DB_PATH)
    migrate(db_path)

    chunks_dir = Path(settings.chunks_dir)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    stations = load_stations()
    for station in stations:
        upsert_station(db_path, station)
    ingestors = create_station_ingestors(
        db_path,
        stations,
        settings,
        chunks_dir=chunks_dir,
    )

    stop_event = threading.Event()

    def _shutdown(_signum: int, _frame: object) -> None:
        stop_event.set()
        for ingestor in ingestors:
            runner = ingestor.runner
            terminate = getattr(runner, "terminate_active", None)
            if callable(terminate):
                terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    threads = [
        threading.Thread(
            target=ingestor.run,
            args=(stop_event,),
            name=f"ingestor-{ingestor.station.name}",
            daemon=True,
        )
        for ingestor in ingestors
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
