"""Apply station control commands from SQLite to running ingestor threads."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ingestor.repository import fetch_station_config, mark_station_disabled, mark_station_recovering
from ingestor.supervisor import StationIngestor, spawn_station_ingestor
from shared.models import PipelineSettings
from shared.station_control import (
    CommandStatus,
    StationControlCommand,
    fetch_pending_commands,
    log_recovery_event,
    mark_command_status,
)

logger = logging.getLogger("ingestor.control")

_SUPPORTED = frozenset(
    {
        StationControlCommand.RESTART.value,
        StationControlCommand.DISABLE.value,
        StationControlCommand.ENABLE.value,
        StationControlCommand.PROMOTE.value,
    }
)
_START_COMMANDS = frozenset(
    {
        StationControlCommand.ENABLE.value,
        StationControlCommand.PROMOTE.value,
    }
)


@dataclass
class IngestorControlContext:
    db_path: Path
    settings: PipelineSettings
    chunks_dir: Path
    threads: dict[str, threading.Thread]
    stop_event: threading.Event


def process_pending_commands(
    db_path: str | Path,
    ingestors: dict[str, StationIngestor],
    *,
    context: IngestorControlContext | None = None,
) -> int:
    """Process pending control commands. Returns number of commands handled."""
    handled = 0
    for command in fetch_pending_commands(db_path):
        command_id = int(command["id"])
        station_id = str(command["station_id"])
        command_name = str(command["command"])
        mark_command_status(db_path, command_id, CommandStatus.PROCESSING)

        if command_name not in _SUPPORTED:
            mark_command_status(
                db_path,
                command_id,
                CommandStatus.FAILED,
                reason=f"unsupported command: {command_name}",
            )
            continue

        if command_name in _START_COMMANDS:
            if context is None:
                mark_command_status(
                    db_path,
                    command_id,
                    CommandStatus.FAILED,
                    reason="enable requires ingestor runtime context",
                )
                continue
            station = fetch_station_config(db_path, station_id)
            if station is None:
                mark_command_status(
                    db_path,
                    command_id,
                    CommandStatus.FAILED,
                    reason="station not found",
                )
                continue
            if not station.enabled:
                mark_command_status(
                    db_path,
                    command_id,
                    CommandStatus.FAILED,
                    reason="station not enabled in database",
                )
                continue
            spawn_station_ingestor(
                db_path=context.db_path,
                station=station,
                settings=context.settings,
                chunks_dir=context.chunks_dir,
                ingestors=ingestors,
                threads=context.threads,
                stop_event=context.stop_event,
            )
            mark_station_recovering(db_path, station_id)
            mark_command_status(db_path, command_id, CommandStatus.DONE)
            log_recovery_event(
                db_path,
                station_id=station_id,
                event_type="station_enabled",
                old_state="standby",
                new_state="recovering",
                reason=command.get("reason") or command_name,
                action_taken=command_name,
            )
            logger.info(
                "station ingest started",
                extra={"station": station_id, "command": command_name, "command_id": command_id},
            )
            handled += 1
            continue

        if command_name == StationControlCommand.DISABLE.value:
            ingestor = ingestors.get(station_id)
            if ingestor is not None:
                ingestor.request_stop()
                ingestors.pop(station_id, None)
            mark_station_disabled(
                db_path,
                station_id,
                reason=command.get("reason") or "station disabled",
            )
            mark_command_status(db_path, command_id, CommandStatus.DONE)
            log_recovery_event(
                db_path,
                station_id=station_id,
                event_type="station_stopped",
                old_state=None,
                new_state="failed",
                reason=command.get("reason") or "station disabled",
                action_taken="disable_station",
            )
            logger.info(
                "station ingest stopped",
                extra={"station": station_id, "command_id": command_id},
            )
            handled += 1
            continue

        ingestor = ingestors.get(station_id)
        if ingestor is None:
            mark_command_status(
                db_path,
                command_id,
                CommandStatus.FAILED,
                reason="station not running in ingestor",
            )
            logger.warning(
                "control command failed: station not active",
                extra={"station": station_id, "command": command_name},
            )
            continue

        if command_name == StationControlCommand.RESTART.value:
            ingestor.request_restart()
            ingestor._apply_restart()
            mark_station_recovering(db_path, station_id)
            mark_command_status(db_path, command_id, CommandStatus.DONE)
            log_recovery_event(
                db_path,
                station_id=station_id,
                event_type="restart_requested",
                old_state=None,
                new_state="recovering",
                reason=command.get("reason") or "manual restart",
                action_taken="restart_station",
            )
            logger.info(
                "station restart requested",
                extra={"station": station_id, "command_id": command_id},
            )
            handled += 1
            continue
    return handled


def run_control_poller(
    db_path: str | Path,
    ingestors: dict[str, StationIngestor],
    stop_event: threading.Event,
    *,
    poll_interval_seconds: float = 60.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    context: IngestorControlContext | None = None,
) -> None:
    """Poll station_control_commands until stop_event is set."""
    interval = max(float(poll_interval_seconds), 1.0)
    while not stop_event.is_set():
        try:
            process_pending_commands(db_path, ingestors, context=context)
        except Exception:
            logger.exception("control command poll failed")
        deadline = time.monotonic() + interval
        while time.monotonic() < deadline:
            if stop_event.is_set():
                return
            sleep_fn(min(0.5, deadline - time.monotonic()))
