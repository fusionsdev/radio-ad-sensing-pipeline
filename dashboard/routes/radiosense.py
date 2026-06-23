"""RadioSense JSON API routes (read-only dashboard APIs + SSE)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from dashboard import metrics_api, queries
from dashboard import radiosense_api
from dashboard.radiosense_errors import api_error_response


def create_radiosense_router(db_path: Path) -> APIRouter:
    router = APIRouter()

    def _require_db() -> None:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")

    @router.get("/api/overview")
    def api_overview() -> JSONResponse:
        return JSONResponse(radiosense_api.fetch_overview_json(db_path))

    @router.get("/api/stations")
    def api_stations(
        enabled: str = "all",
        status: str = "all",
        limit: int = 100,
    ) -> JSONResponse:
        try:
            _require_db()
            return JSONResponse(
                radiosense_api.fetch_stations_json(
                    db_path, enabled=enabled, status=status, limit=limit
                )
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise api_error_response(
                route="/api/stations",
                exc=exc,
                db_path=db_path,
                query_name="fetch_stations_json",
                detail_key="stations_api_failed",
                message="Failed to load stations",
            ) from exc

    @router.get("/api/detections")
    def api_detections(
        limit: int = 100,
        offset: int = 0,
        station: str | None = None,
        since: str | None = None,
        q: str | None = None,
        min_confidence: float | None = None,
    ) -> JSONResponse:
        _require_db()
        return JSONResponse(
            radiosense_api.fetch_detections_json(
                db_path,
                limit=limit,
                offset=offset,
                station=station,
                since=since,
                q=q,
                min_confidence=min_confidence,
            )
        )

    @router.get("/api/keyword-candidates")
    def api_keyword_candidates(
        source: str = "all",
        status: str | None = None,
        min_score: float | None = None,
        limit: int = 200,
        offset: int = 0,
        q: str | None = None,
    ) -> JSONResponse:
        _require_db()
        return JSONResponse(
            radiosense_api.fetch_keyword_candidates_json(
                db_path,
                source=source,
                status=status,
                min_score=min_score,
                limit=limit,
                offset=offset,
                q=q,
            )
        )

    @router.get("/api/advertisers")
    def api_advertisers(
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        vertical: str | None = None,
        q: str | None = None,
    ) -> JSONResponse:
        _require_db()
        return JSONResponse(
            radiosense_api.fetch_advertisers_json(
                db_path,
                limit=limit,
                offset=offset,
                status=status,
                vertical=vertical,
                q=q,
            )
        )

    @router.get("/api/advertisers/{advertiser_id}")
    def api_advertiser_detail(advertiser_id: int) -> JSONResponse:
        _require_db()
        detail = radiosense_api.fetch_advertiser_detail_json(db_path, advertiser_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Advertiser not found")
        return JSONResponse(detail)

    @router.get("/api/exports")
    def api_exports() -> JSONResponse:
        return JSONResponse(radiosense_api.fetch_exports_json())

    @router.get("/api/exports/{filename}")
    def api_export_file(filename: str) -> FileResponse:
        path = radiosense_api.resolve_export_path(filename)
        if path is None:
            raise HTTPException(status_code=404, detail="Export file not found")
        return FileResponse(
            path,
            media_type=radiosense_api.export_media_type(path),
            filename=path.name,
        )

    @router.get("/api/watchdog")
    def api_watchdog() -> JSONResponse:
        _require_db()
        return JSONResponse(radiosense_api.fetch_watchdog_json(db_path))

    @router.get("/api/metrics/summary")
    def api_metrics_summary() -> JSONResponse:
        return JSONResponse(metrics_api.fetch_metrics_summary(db_path))

    @router.get("/api/metrics/prometheus")
    def api_metrics_prometheus(key: str) -> JSONResponse:
        payload = metrics_api.fetch_prometheus_metric(key)
        if "error" in payload and "allowed_keys" in payload:
            raise HTTPException(status_code=400, detail=payload["error"])
        status_code = 200
        if payload.get("error") == "Prometheus unavailable":
            status_code = 503
        return JSONResponse(payload, status_code=status_code)

    @router.get("/api/metrics/grafana-links")
    def api_metrics_grafana_links() -> JSONResponse:
        return JSONResponse(metrics_api.fetch_grafana_links())

    @router.get("/api/live/events")
    async def api_live_events(request: Request) -> StreamingResponse:
        async def event_stream():
            while True:
                if await request.is_disconnected():
                    break
                payload = radiosense_api.build_live_event(db_path)
                yield f"data: {json.dumps(payload, default=str)}\n\n"
                await asyncio.sleep(3)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
