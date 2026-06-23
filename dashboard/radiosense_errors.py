"""Structured API error logging and sanitized client responses."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger("radiosense.api")


def log_route_failure(
    *,
    route: str,
    exc: Exception,
    db_path: Path,
    query_name: str,
) -> str:
    request_id = uuid.uuid4().hex[:12]
    logger.error(
        "route=%s exception_type=%s message=%s db_path=%s query_name=%s request_id=%s timestamp=%s",
        route,
        type(exc).__name__,
        str(exc),
        str(db_path),
        query_name,
        request_id,
        __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
    )
    return request_id


def api_error_response(
    *,
    route: str,
    exc: Exception,
    db_path: Path,
    query_name: str,
    detail_key: str,
    message: str,
    status_code: int = 500,
) -> HTTPException:
    request_id = log_route_failure(route=route, exc=exc, db_path=db_path, query_name=query_name)
    return HTTPException(
        status_code=status_code,
        detail={
            "detail": detail_key,
            "message": message,
            "request_id": request_id,
        },
    )