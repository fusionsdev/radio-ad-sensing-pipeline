"""Entrypoint: python -m ingestor"""

from __future__ import annotations

import signal
import sys
import threading
from pathlib import Path

from ingestor.control import IngestorControlContext, run_control_poller
from ingestor.repository import upsert_station
from ingestor.supervisor import create_station_ingestors, run_station_ingestor, startup_stagger_delay_seconds
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
    ingestors_by_name = {ingestor.station.name: ingestor for ingestor in ingestors}
    threads_by_name: dict[str, threading.Thread] = {}

    stop_event = threading.Event()
    control_context = IngestorControlContext(
        db_path=db_path,
        settings=settings,
        chunks_dir=chunks_dir,
        threads=threads_by_name,
        stop_event=stop_event,
    )

    def _shutdown(_signum: int, _frame: object) -> None:
        stop_event.set()
        for ingestor in ingestors:
            runner = ingestor.runner
            terminate = getattr(runner, "terminate_active", None)
            if callable(terminate):
                terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    control_thread = threading.Thread(
        target=run_control_poller,
        args=(db_path, ingestors_by_name, stop_event),
        kwargs={
            "poll_interval_seconds": float(settings.watchdog.health_check_interval_seconds),
            "context": control_context,
        },
        name="ingestor-control",
        daemon=True,
    )
    control_thread.start()

    threads = [
        threading.Thread(
            target=run_station_ingestor,
            args=(
                ingestor,
                stop_event,
            ),
            kwargs={
                "startup_delay_sec": startup_stagger_delay_seconds(
                    index,
                    float(settings.ingest_startup_stagger_sec),
                ),
            },
            name=f"ingestor-{ingestor.station.name}",
            daemon=True,
        )
        for index, ingestor in enumerate(ingestors)
    ]
    for index, thread in enumerate(threads):
        threads_by_name[ingestors[index].station.name] = thread
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
