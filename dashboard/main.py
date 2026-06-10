"""FastAPI read-only dashboard over SQLite."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from dashboard import queries
from shared.config import load_settings
from shared.metrics import configure_dashboard_metrics, start_metrics_server

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")


def create_app(db_path: Path | None = None) -> FastAPI:
    settings = load_settings()
    resolved_db = (
        db_path
        if db_path is not None
        else (PROJECT_ROOT / settings.db_path).resolve()
    )

    app = FastAPI(title="Radio Ad-Sensing Dashboard", docs_url=None, redoc_url=None)
    start_metrics_server(9104)
    configure_dashboard_metrics(resolved_db)

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse(queries.fetch_health(resolved_db))

    @app.get("/audio/{resource_id}")
    def audio(resource_id: int) -> FileResponse:
        if not queries.db_exists(resolved_db):
            raise HTTPException(status_code=404, detail="Database not available")
        path = queries.resolve_audio_path(resolved_db, resource_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Audio not found")
        return FileResponse(path)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        stats = queries.fetch_overview(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "stats": stats,
                "format_ts": _format_ts,
                "format_age": _format_age,
                "format_status": _format_status,
            },
        )

    @app.get("/ads", response_class=HTMLResponse)
    def ads_list(request: Request, page: int = 1) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        ads, total = queries.fetch_ads_page(resolved_db, page=page)
        total_pages = max(1, (total + queries.ADS_PAGE_SIZE - 1) // queries.ADS_PAGE_SIZE)
        context = {
            "ads": ads,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "format_ts": _format_ts,
        }
        template = "partials/ads_rows.html" if request.headers.get("HX-Request") else "ads.html"
        return TEMPLATES.TemplateResponse(request, template, context)

    @app.get("/ads/{ad_id}", response_class=HTMLResponse)
    def ad_detail(request: Request, ad_id: int) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        ad, detections, archived_path = queries.fetch_ad_detail(resolved_db, ad_id)
        if ad is None:
            raise HTTPException(status_code=404, detail="Ad not found")
        has_audio = archived_path is not None and queries.resolve_audio_path(
            resolved_db, ad_id
        )
        return TEMPLATES.TemplateResponse(
            request,
            "ad_detail.html",
            {
                "ad": ad,
                "detections": detections,
                "has_audio": has_audio is not None,
                "format_ts": _format_ts,
            },
        )

    @app.get("/stations", response_class=HTMLResponse)
    def stations(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        rows = queries.fetch_stations(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "stations.html",
            {
                "stations": rows,
                "format_ts": _format_ts,
                "format_age": _format_age,
                "format_status": _format_status,
            },
        )

    @app.get("/gaps", response_class=HTMLResponse)
    def gaps(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        rows = queries.fetch_gaps(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "gaps.html",
            {"gaps": rows, "format_ts": _format_ts},
        )

    app.state.db_path = resolved_db
    return app


def _no_database(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "no_database.html", {}, status_code=200)


def _format_ts(ts: float | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")


def _format_age(seconds: float | None) -> str:
    if seconds is None:
        return "no chunks yet"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    return f"{seconds / 3600:.1f}h ago"


def _format_status(status: str) -> str:
    labels = {
        "live": ("Live", "ok"),
        "stale": ("Stale", "warn"),
        "down": ("Down", "err"),
        "waiting": ("Starting", "warn"),
        "disabled": ("Off", "muted"),
    }
    label, css = labels.get(status, (status.title(), "muted"))
    return f'<span class="badge {css}">{label}</span>'
