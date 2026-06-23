"""HTTP client for the host-side RadioSense control bridge."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

CONTROL_BRIDGE_URL = os.getenv(
    "RADIOSENSE_CONTROL_URL",
    "http://host.docker.internal:8792",
).rstrip("/")
CONTROL_BRIDGE_TIMEOUT = float(os.getenv("RADIOSENSE_CONTROL_TIMEOUT_SECONDS", "30"))
OFFLINE_PAYLOAD = {
    "ok": False,
    "error": "RadioSense control bridge is offline",
    "recommended_command": (
        r"cd H:\DEV\projects\radio-ad-sensing-pipeline && "
        r".\scripts\start-radiosense-control-bridge.ps1 -Background"
    ),
}

ALLOWED_ACTIONS = {
    "start-hermes-bridge",
    "restart-dashboard",
    "start-frontend",
    "open-grafana",
    "open-prometheus",
    "open-backend-health",
    "open-dashboard-logs",
    "recheck",
    "test-hermes",
}


def _request(
    method: str,
    path: str,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    url = f"{CONTROL_BRIDGE_URL}{path}"
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout or CONTROL_BRIDGE_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {"ok": True}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"ok": False, "error": raw or str(exc)}
        payload.setdefault("ok", False)
        return payload
    except (urllib.error.URLError, TimeoutError, OSError):
        return dict(OFFLINE_PAYLOAD)


def fetch_control_status() -> dict[str, Any]:
    return _request("GET", "/status")


def run_control_action(action: str) -> dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        return {"ok": False, "error": f"Unknown action: {action}"}
    return _request("POST", f"/action/{action}", timeout=180)