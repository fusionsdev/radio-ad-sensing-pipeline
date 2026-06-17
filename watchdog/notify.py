"""Telegram ops alerts for the station watchdog."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from shared.config import load_telegram_settings
from shared.models import WatchdogSettings
from watchdog.health import StationHealthSnapshot


@dataclass(frozen=True)
class QueueSnapshot:
    done: int
    dropped: int
    pending: int
    drop_ratio: float
    level: str


def send_stale_station_alert(
    snap: StationHealthSnapshot,
    *,
    active_count: int,
    target_count: int,
    queue: QueueSnapshot,
    stale_minutes: int,
    recovery_action: str | None = None,
    settings: WatchdogSettings | None = None,
) -> bool:
    """Send a watchdog stale alert. Returns True when sent (or dry-run)."""
    watchdog_settings = settings or WatchdogSettings()
    telegram = load_telegram_settings()
    token = telegram.telegram_bot_token
    chat_id = telegram.telegram_chat_id
    if not token or not chat_id:
        return False

    age_line = (
        f"No chunk received for {int((snap.age_seconds or 0) // 60)} minutes."
        if snap.age_seconds is not None
        else "No chunks recorded for this station."
    )
    action_line = _format_recovery_action(recovery_action, watchdog_settings)
    text = (
        "Station Watchdog Alert\n\n"
        f"Problem:\n{snap.station_name} became stale.\n"
        f"{age_line}\n\n"
        f"Action:\n{action_line}\n\n"
        f"Active stations:\n{active_count}/{target_count}\n\n"
        f"Queue:\n"
        f"done {queue.done} / dropped {queue.dropped} / pending {queue.pending}\n"
        f"drop ratio: {queue.level} ({queue.drop_ratio})\n\n"
        f"Next:\n{_next_step(recovery_action, queue.level)}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except urllib.error.URLError:
        return False


def _format_recovery_action(recovery_action: str | None, settings: WatchdogSettings) -> str:
    if recovery_action == "restart_queued":
        return "Auto-restart queued for ingestor (restart_station command)."
    if recovery_action == "restart_pending":
        return "Restart already pending for this station."
    if recovery_action == "disabled":
        return "Station disabled after repeated failures; cooldown applied."
    if recovery_action == "cooldown_skip":
        return "Station in cooldown; auto-restart skipped."
    if not settings.auto_restart_on_stale:
        return f"Stale detected (threshold {settings.station_stale_after_minutes} min). Auto-restart disabled."
    return f"Stale detected (threshold {settings.station_stale_after_minutes} min). Monitoring only."


def _next_step(recovery_action: str | None, queue_level: str) -> str:
    if recovery_action == "disabled":
        return "Review station stream URL before re-enabling."
    if queue_level == "critical":
        return "Queue pressure critical; backup promotion remains paused."
    if recovery_action == "restart_queued":
        return "Ingestor will restart ffmpeg for this station on next command poll."
    return "Watchdog will retry on the next stale episode if recovery fails."
