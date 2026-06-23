"""Read-only Memory OS API for dashboard consumers."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from tools.memory.vault_reader import (
    fetch_decisions,
    fetch_harness_latest,
    fetch_incidents,
    fetch_memory_health,
    fetch_memory_status,
    fetch_station_memories,
)


def create_memory_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/memory/health")
    def api_memory_health() -> JSONResponse:
        return JSONResponse(fetch_memory_health())

    @router.get("/api/memory/status")
    def api_memory_status() -> JSONResponse:
        return JSONResponse(fetch_memory_status())

    @router.get("/api/memory/harness/latest")
    def api_memory_harness_latest() -> JSONResponse:
        return JSONResponse(fetch_harness_latest())

    @router.get("/api/memory/decisions")
    def api_memory_decisions(
        limit: int = Query(default=10, ge=1, le=100),
    ) -> JSONResponse:
        return JSONResponse({"rows": fetch_decisions(limit=limit)})

    @router.get("/api/memory/incidents")
    def api_memory_incidents(
        limit: int = Query(default=10, ge=1, le=100),
    ) -> JSONResponse:
        return JSONResponse({"rows": fetch_incidents(limit=limit)})

    @router.get("/api/memory/stations")
    def api_memory_stations(
        limit: int = Query(default=20, ge=1, le=100),
    ) -> JSONResponse:
        return JSONResponse({"rows": fetch_station_memories(limit=limit)})

    return router