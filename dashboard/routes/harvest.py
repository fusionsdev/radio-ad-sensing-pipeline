"""Radio Harvest Control dashboard routes.

Exposes a JSON API that wraps ``scripts/harvest_control.py`` behind a fixed
command allowlist, plus operator-facing HTML pages. Action buttons POST to
``/radio-harvest/<action>`` and redirect (303) back to the control panel with
a flash message — the same pattern used by ``/ops/watchdog/restart``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard import harvest_api
from dashboard import queries

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

FLASH = {
    "probe_ok": "Probe finished.",
    "probe_fail": "Probe failed — see details.",
    "start_ok": "Overnight harvest started.",
    "start_fail": "Failed to start harvest.",
    "stop_ok": "Harvest stopped.",
    "stop_fail": "Failed to stop harvest.",
    "already_running": "Harvest already running — not starting a second session.",
}


def create_harvest_router(
    db_path: Path,
    *,
    format_ts,
    no_database_handler,
) -> APIRouter:
    router = APIRouter()

    def _fmt_conf(value) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):.0%}"
        except (TypeError, ValueError):
            return str(value)

    def _fmt_age(seconds) -> str:
        if seconds is None:
            return "—"
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            return "—"
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            return f"{int(seconds // 60)}m"
        return f"{seconds / 3600:.1f}h"

    def _fmt_when(value) -> str:
        """Format either an epoch float or an ISO-8601 string (status file)."""
        if value is None or value == "":
            return "—"
        if isinstance(value, (int, float)):
            return format_ts(value)
        # ISO string from runtime/harvest_status.json
        text = str(value)
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return text

    def _context_base() -> dict[str, object]:
        return {
            "format_ts": format_ts,
            "fmt_conf": _fmt_conf,
            "fmt_age": _fmt_age,
            "fmt_when": _fmt_when,
        }

    # ------------------------------------------------------------------ HTML

    @router.get("/radio-harvest", response_class=HTMLResponse)
    def control_panel(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        status = harvest_api.fetch_harvest_status(db_path)
        per_station = harvest_api.fetch_per_station(db_path)
        flash_key = request.query_params.get("msg")
        flash = FLASH.get(flash_key, "") if flash_key else ""
        detail = request.query_params.get("detail") or ""
        return TEMPLATES.TemplateResponse(
            request,
            "harvest/index.html",
            {
                **_context_base(),
                "status": status,
                "per_station": per_station,
                "flash": flash,
                "flash_detail": detail,
                "running": status.get("running") is True,
                "allowed_actions": harvest_api.allowed_actions(),
                "warning": harvest_api.harvest_warning(status),
            },
        )

    @router.get("/radio-harvest/status", response_class=HTMLResponse)
    def status_page(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        status = harvest_api.fetch_harvest_status(db_path)
        return TEMPLATES.TemplateResponse(
            request,
            "harvest/status.html",
            {**_context_base(), "status": status},
        )

    @router.get("/radio-harvest/detections", response_class=HTMLResponse)
    def detections_page(request: Request, limit: int = 50) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        rows = harvest_api.fetch_harvest_detections(db_path, limit=max(1, min(limit, 500)))
        return TEMPLATES.TemplateResponse(
            request,
            "harvest/detections.html",
            {**_context_base(), "rows": rows, "limit": limit},
        )

    @router.get("/radio-harvest/queue", response_class=HTMLResponse)
    def queue_page(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        health = harvest_api.fetch_queue_health_detail(db_path)
        return TEMPLATES.TemplateResponse(
            request,
            "harvest/queue.html",
            {**_context_base(), "health": health},
        )

    @router.get("/radio-harvest/stations", response_class=HTMLResponse)
    def stations_config_page(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        stations = harvest_api.fetch_station_config()
        enabled_count = sum(1 for s in stations if s["enabled"])
        return TEMPLATES.TemplateResponse(
            request,
            "harvest/stations.html",
            {
                "stations": stations,
                "enabled_count": enabled_count,
                "total_count": len(stations),
            },
        )

    # -------------------------------------------------------- action buttons

    def _redirect(msg: str, detail: str = "") -> RedirectResponse:
        url = f"/radio-harvest?msg={msg}"
        if detail:
            # keep the detail short to avoid URL overflow
            url += f"&detail={detail[:300]}"
        return RedirectResponse(url=url, status_code=303)

    @router.post("/radio-harvest/probe")
    def action_probe() -> RedirectResponse:
        result = harvest_api.run_control_action("probe")
        if result.get("ok"):
            return _redirect("probe_ok", (result.get("stdout") or "").strip()[:300])
        return _redirect("probe_fail", (result.get("stderr") or result.get("stdout") or "").strip()[:300])

    @router.post("/radio-harvest/start")
    def action_start() -> RedirectResponse:
        try:
            result = harvest_api.run_control_action("start")
        except harvest_api.HarvestAlreadyRunningError:
            return _redirect("already_running")
        if result.get("ok"):
            return _redirect("start_ok")
        return _redirect("start_fail", (result.get("stderr") or result.get("stdout") or "").strip()[:300])

    @router.post("/radio-harvest/stop")
    def action_stop() -> RedirectResponse:
        result = harvest_api.run_control_action("stop")
        if result.get("ok"):
            return _redirect("stop_ok")
        return _redirect("stop_fail", (result.get("stderr") or result.get("stdout") or "").strip()[:300])

    # ------------------------------------------------------------------ JSON

    @router.post("/api/harvest/probe")
    def api_probe() -> JSONResponse:
        return JSONResponse(harvest_api.run_control_action("probe"))

    @router.post("/api/harvest/start")
    def api_start() -> JSONResponse:
        try:
            return JSONResponse(harvest_api.run_control_action("start"))
        except harvest_api.HarvestAlreadyRunningError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)

    @router.post("/api/harvest/stop")
    def api_stop() -> JSONResponse:
        return JSONResponse(harvest_api.run_control_action("stop"))

    @router.get("/api/harvest/status")
    def api_status() -> JSONResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        return JSONResponse(harvest_api.fetch_harvest_status(db_path))

    @router.get("/api/harvest/detections")
    def api_detections(limit: int = 50) -> JSONResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        rows = harvest_api.fetch_harvest_detections(db_path, limit=max(1, min(limit, 500)))
        return JSONResponse({"rows": rows, "count": len(rows)})

    @router.get("/api/harvest/queue-health")
    def api_queue_health() -> JSONResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        return JSONResponse(harvest_api.fetch_queue_health_detail(db_path))

    @router.get("/api/harvest/stations")
    def api_stations() -> JSONResponse:
        return JSONResponse({"stations": harvest_api.fetch_station_config()})

    return router
