"""Hermes AI analyze route."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dashboard import hermes_client


class HermesAnalyzeRequest(BaseModel):
    command: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1)
    context: dict[str, Any] | None = None


def create_hermes_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/hermes/analyze")
    def api_hermes_analyze(body: HermesAnalyzeRequest) -> JSONResponse:
        result = hermes_client.analyze_prompt(
            command=body.command.strip(),
            prompt=body.prompt,
            context=body.context,
        )
        status_code = 200 if result.get("ok") else 503
        return JSONResponse(result, status_code=status_code)

    return router