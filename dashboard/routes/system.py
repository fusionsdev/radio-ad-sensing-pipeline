"""RadioSense system control proxy routes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from dashboard import queries, system_client
from dashboard import system_health


def _now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".") + "Z"


def _status_level(value: str) -> str:
    normalized = value.lower()
    if normalized in {"online", "ok", "healthy", "running", "connected"}:
        return "ok"
    if normalized in {"stopped", "degraded", "warning", "unhealthy"}:
        return "warning"
    if normalized in {"offline", "down", "error", "failed", "critical", "disconnected"}:
        return "critical"
    return "unknown"


def _component_row(
    *,
    key: str,
    component: str,
    expected: str,
    probe: dict[str, Any] | None,
    checked_at: str,
    action: str,
    status_override: str | None = None,
) -> dict[str, Any]:
    probe = probe or {}
    if status_override:
        status = status_override
    elif probe.get("ok"):
        status = "ok"
    elif probe.get("status"):
        status = str(probe.get("status"))
    else:
        status = "error"
    return {
        "key": key,
        "component": component,
        "expected": expected,
        "status": status,
        "level": _status_level("ok" if probe.get("ok") else "error"),
        "last_checked": checked_at,
        "last_error": probe.get("error"),
        "action": action,
    }


def create_system_router(db_path: Path) -> APIRouter:
    router = APIRouter(prefix="/api/system")

    def _merge_status(control_payload: dict[str, Any]) -> dict[str, Any]:
        checked_at = _now_iso()
        classifier = system_health.build_status_payload(db_path, control_payload, checked_at=checked_at)
        components = classifier["components"]
        health = queries.fetch_health(db_path)
        harvest = None
        harvest_error = None
        try:
            from dashboard import harvest_api  # noqa: PLC0415

            if queries.db_exists(db_path):
                harvest = harvest_api.fetch_harvest_status(db_path)
            else:
                harvest_error = "Database not available"
        except Exception as exc:  # noqa: BLE001
            harvest_error = str(exc)

        control_components = (control_payload.get("components") or {}) if control_payload.get("ok") else {}
        rows = [
            _component_row(
                key="backend_api",
                component="Backend API",
                expected="/health",
                probe=components.get("backend_health"),
                checked_at=checked_at,
                action="restart-dashboard",
                status_override="online" if components.get("backend_health", {}).get("ok") else "offline",
            ),
            _component_row(
                key="sqlite_db",
                component="DB",
                expected="/health db_reachable",
                probe={
                    "ok": bool(health.get("db_reachable")),
                    "error": None if health.get("db_reachable") else "db_reachable=false",
                },
                checked_at=checked_at,
                action="open-pipeline-health",
                status_override="ok" if health.get("db_reachable") else "error",
            ),
            _component_row(
                key="stations_api",
                component="Stations API",
                expected="/api/stations?limit=1",
                probe=components.get("stations_api"),
                checked_at=checked_at,
                action="restart-dashboard",
            ),
            _component_row(
                key="detections_api",
                component="Detections API",
                expected="/api/detections?limit=1",
                probe=components.get("detections_api"),
                checked_at=checked_at,
                action="restart-dashboard",
            ),
            _component_row(
                key="hermes_bridge",
                component="Hermes Bridge",
                expected="host.docker.internal:8791/health",
                probe=components.get("hermes_bridge"),
                checked_at=checked_at,
                action="start-hermes-bridge",
                status_override="online" if components.get("hermes_bridge", {}).get("ok") else "offline",
            ),
            _component_row(
                key="control_bridge",
                component="Control Bridge",
                expected="host.docker.internal:8792/health",
                probe=components.get("control_bridge"),
                checked_at=checked_at,
                action="recheck",
                status_override="online" if components.get("control_bridge", {}).get("ok") else "offline",
            ),
            {
                "key": "local_hermes",
                "component": "Local Hermes",
                "expected": "hermes -p radio-runner via bridge",
                "status": "unknown",
                "level": "unknown",
                "last_checked": checked_at,
                "last_error": None,
                "action": "test-hermes",
            },
            {
                "key": "frontend",
                "component": "Frontend",
                "expected": "localhost:5150",
                "status": (control_components.get("frontend") or {}).get("status", "unknown"),
                "level": _status_level((control_components.get("frontend") or {}).get("status", "unknown")),
                "last_checked": (control_components.get("checked_at") or checked_at),
                "last_error": None,
                "action": "open-frontend",
            },
            {
                "key": "docker_dashboard",
                "component": "Docker Dashboard Container",
                "expected": "radio-dashboard",
                "status": (control_components.get("docker_dashboard") or {}).get("status", "unknown"),
                "level": _status_level((control_components.get("docker_dashboard") or {}).get("status", "unknown")),
                "last_checked": (control_components.get("checked_at") or checked_at),
                "last_error": None,
                "action": "restart-dashboard",
            },
            {
                "key": "harvest",
                "component": "Harvest",
                "expected": "/api/harvest/status",
                "status": (
                    (harvest or {}).get("status", "unknown")
                    if harvest is not None
                    else "error"
                ),
                "level": _status_level(
                    (harvest or {}).get("status", "error") if harvest is not None else "error"
                ),
                "last_checked": checked_at,
                "last_error": harvest_error,
                "action": "open-harvest",
            },
        ]

        interpretations: list[dict[str, str]] = []
        failure_class = classifier["failure_class"]
        if failure_class == "partial_backend_failure":
            failed = [
                name
                for name, probe in components.items()
                if name.endswith("_api") and not (probe or {}).get("ok")
            ]
            interpretations.append(
                {
                    "title": "Partial backend failure",
                    "message": (
                        f"Backend /health is reachable but API routes failed: {', '.join(failed) or 'unknown'}.\n"
                        "Recommended actions:\n"
                        "1. Auto-heal: Restart Dashboard API\n"
                        "2. Open dashboard logs\n"
                        "3. Export healing report for Hermes"
                    ),
                }
            )
        if failure_class == "control_bridge_offline":
            interpretations.append(
                {
                    "title": "Control bridge offline",
                    "message": (
                        "RadioSense control bridge is offline.\n"
                        "Run start-radiosense-control-bridge.ps1 -Background or the stack launcher."
                    ),
                }
            )
        if failure_class == "hermes_bridge_offline":
            interpretations.append(
                {
                    "title": "Hermes bridge offline",
                    "message": (
                        "Hermes bridge is offline.\n"
                        "Run start-hermes-bridge.ps1 -Background or click Start Bridge."
                    ),
                }
            )
        if failure_class == "db_unreachable":
            interpretations.append(
                {
                    "title": "Database unreachable",
                    "message": (
                        "Backend reports db_reachable=false.\n"
                        "Safe recovery: restart dashboard container only. Do not delete DB or chunks."
                    ),
                }
            )
        if failure_class == "backend_offline":
            interpretations.append(
                {
                    "title": "Backend offline",
                    "message": (
                        "Backend /health is unreachable from the classifier.\n"
                        "Run the stack launcher script from the host."
                    ),
                }
            )

        stations_probe = components.get("stations_api") or {}
        return {
            **classifier,
            "health": health,
            "harvest": harvest,
            "errors": {
                "stations": stations_probe.get("error"),
                "harvest": harvest_error,
            },
            "rows": rows,
            "recent_actions": control_payload.get("recent_actions", []),
            "interpretations": interpretations,
            "control_components": control_components,
        }

    @router.get("/status")
    def api_system_status() -> JSONResponse:
        control_payload = system_client.fetch_control_status()
        payload = _merge_status(control_payload)
        if not control_payload.get("ok"):
            payload["control_bridge_online"] = False
            payload["control_bridge_error"] = control_payload.get("error")
            payload["recommended_command"] = control_payload.get("recommended_command")
        return JSONResponse(payload)

    @router.post("/action/{action_name}")
    def api_system_action(action_name: str) -> JSONResponse:
        if action_name not in system_client.ALLOWED_ACTIONS:
            raise HTTPException(status_code=404, detail=f"Unknown action: {action_name}")
        result = system_client.run_control_action(action_name)
        status_code = 200 if result.get("ok") else 503
        if result.get("error") == system_client.OFFLINE_PAYLOAD["error"]:
            status_code = 503
        return JSONResponse(result, status_code=status_code)

    return router