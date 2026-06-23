"""Route health probes and failure classification for RadioSense self-healing."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dashboard import harvest_api, queries, radiosense_api

HERMES_BRIDGE_URL = os.getenv("HERMES_BRIDGE_URL", "http://host.docker.internal:8791").rstrip("/")
CONTROL_BRIDGE_URL = os.getenv("RADIOSENSE_CONTROL_URL", "http://host.docker.internal:8792").rstrip("/")
PROBE_TIMEOUT = float(os.getenv("RADIOSENSE_PROBE_TIMEOUT_SECONDS", "5"))


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"


def _http_probe(url: str, *, timeout: float | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout or PROBE_TIMEOUT) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "error": None,
                "body": body[:500],
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "error": body[:300] or str(exc),
            "body": body[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "error": str(exc), "body": None}


def _probe_internal(
    label: str,
    fn: Any,
    *,
    requires_db: bool = True,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if requires_db and db_path is not None and not queries.db_exists(db_path):
        return {"ok": False, "status": 503, "error": "Database not available"}
    try:
        fn()
        return {"ok": True, "status": 200, "error": None}
    except Exception as exc:  # noqa: BLE001
        status = 503 if "not available" in str(exc).lower() else 500
        return {"ok": False, "status": status, "error": str(exc)}


def probe_all_components(db_path: Path, control_payload: dict[str, Any]) -> dict[str, Any]:
    """Probe backend routes and external bridges; return structured component health."""
    health = queries.fetch_health(db_path)
    backend_health = {
        "ok": health.get("status") == "ok",
        "status": 200 if health.get("status") == "ok" else 503,
        "error": None if health.get("status") == "ok" else "health check failed",
        "db_reachable": bool(health.get("db_reachable")),
    }

    stations = _probe_internal(
        "stations",
        lambda: radiosense_api.fetch_stations_json(db_path, limit=1),
        db_path=db_path,
    )
    detections = _probe_internal(
        "detections",
        lambda: radiosense_api.fetch_detections_json(db_path, limit=1),
        db_path=db_path,
    )
    overview = _probe_internal(
        "overview",
        lambda: radiosense_api.fetch_overview_json(db_path),
        db_path=db_path,
    )
    harvest_status = _probe_internal(
        "harvest_status",
        lambda: harvest_api.fetch_harvest_status(db_path),
        db_path=db_path,
    )
    queue_health = _probe_internal(
        "queue_health",
        lambda: harvest_api.fetch_queue_health_detail(db_path),
        db_path=db_path,
    )

    hermes = _http_probe(f"{HERMES_BRIDGE_URL}/health")
    control_online = bool(control_payload.get("ok"))
    control_probe = (
        {"ok": True, "status": 200, "error": None}
        if control_online
        else _http_probe(f"{CONTROL_BRIDGE_URL}/health")
    )

    sse_note = "sse availability is tracked by the frontend live events hook"
    sse_ok = all(
        item.get("ok")
        for item in (overview, stations, detections)
        if item is not None
    )

    return {
        "backend_health": backend_health,
        "overview_api": overview,
        "stations_api": stations,
        "detections_api": detections,
        "harvest_status_api": harvest_status,
        "queue_health_api": queue_health,
        "sse": {"ok": sse_ok, "error": None if sse_ok else "disconnected", "note": sse_note},
        "hermes_bridge": {
            "ok": hermes.get("ok", False),
            "status": hermes.get("status"),
            "error": hermes.get("error"),
        },
        "control_bridge": {
            "ok": control_probe.get("ok", False),
            "status": control_probe.get("status"),
            "error": control_probe.get("error") or control_payload.get("error"),
        },
    }


def classify_failure(components: dict[str, Any]) -> tuple[str, str, str]:
    """Return (overall_status, failure_class, recommended_action)."""
    backend = components.get("backend_health") or {}
    if not backend.get("ok"):
        if not backend.get("db_reachable"):
            return "critical", "db_unreachable", "restart-dashboard"
        return "critical", "backend_offline", "show-startup-command"

    control = components.get("control_bridge") or {}
    if not control.get("ok"):
        return "critical", "control_bridge_offline", "show-control-bridge-command"

    hermes = components.get("hermes_bridge") or {}
    if not hermes.get("ok"):
        return "warning", "hermes_bridge_offline", "start-hermes-bridge"

    api_keys = ("stations_api", "detections_api", "overview_api", "harvest_status_api", "queue_health_api")
    failed_apis = [key for key in api_keys if not (components.get(key) or {}).get("ok")]
    if failed_apis:
        return "critical", "partial_backend_failure", "restart-dashboard"

    sse = components.get("sse") or {}
    if not sse.get("ok"):
        return "warning", "sse_offline", "reconnect-sse"

    return "ok", "healthy", "none"


def safe_actions_for(
    failure_class: str,
    *,
    control_bridge_online: bool,
) -> list[str]:
    actions: list[str] = ["recheck", "export-report", "ask-hermes"]
    if not control_bridge_online:
        return ["export-report", "ask-hermes", "show-startup-command"]

    if failure_class in {"partial_backend_failure", "db_unreachable", "backend_offline"}:
        actions.insert(0, "restart-dashboard")
    if failure_class == "hermes_bridge_offline":
        actions.insert(0, "start-hermes-bridge")
    if failure_class == "sse_offline":
        actions.insert(0, "reconnect-sse")
    if failure_class == "frontend_cache_stale":
        actions.insert(0, "clear-cache")
    if failure_class in {"partial_backend_failure", "db_unreachable"}:
        actions.append("open-dashboard-logs")
    return actions


def build_status_payload(
    db_path: Path,
    control_payload: dict[str, Any],
    *,
    checked_at: str | None = None,
) -> dict[str, Any]:
    components = probe_all_components(db_path, control_payload)
    overall_status, failure_class, recommended_action = classify_failure(components)
    control_online = bool(control_payload.get("ok")) or bool(
        (components.get("control_bridge") or {}).get("ok")
    )
    safe_actions = safe_actions_for(failure_class, control_bridge_online=control_online)
    ok = failure_class == "healthy"

    return {
        "ok": ok,
        "overall_status": overall_status,
        "failure_class": failure_class,
        "recommended_action": recommended_action,
        "components": components,
        "safe_actions": safe_actions,
        "checked_at": checked_at or _now_iso(),
        "startup_command": control_payload.get(
            "startup_command",
            "cd H:\\DEV\\projects\\radio-ad-sensing-pipeline\n"
            ".\\scripts\\start-radiosense-stack.ps1 -OpenBrowser",
        ),
        "control_bridge_online": control_online,
        "control_bridge_error": None if control_online else control_payload.get("error"),
        "recommended_command": control_payload.get("recommended_command"),
    }