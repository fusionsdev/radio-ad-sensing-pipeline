"""FastAPI read-only dashboard over SQLite."""

from __future__ import annotations

import base64
import binascii
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).parent / "static"),
        name="static",
    )
    start_metrics_server(9104)
    configure_dashboard_metrics(resolved_db)

    # The dashboard is read-only; schema ownership belongs to writer processes.
    auth_user = os.environ.get("DASHBOARD_BASIC_AUTH_USERNAME")
    auth_pass = os.environ.get("DASHBOARD_BASIC_AUTH_PASSWORD")
    if auth_user and auth_pass:

        @app.middleware("http")
        async def _basic_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.url.path == "/health":
                return await call_next(request)
            header = request.headers.get("authorization", "")
            authorized = False
            if header.startswith("Basic "):
                try:
                    decoded = base64.b64decode(header[6:]).decode("utf-8")
                except (binascii.Error, ValueError, UnicodeDecodeError):
                    decoded = ""
                user, _, password = decoded.partition(":")
                authorized = secrets.compare_digest(
                    user, auth_user
                ) and secrets.compare_digest(password, auth_pass)
            if not authorized:
                return Response(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="dashboard"'},
                )
            return await call_next(request)

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
                "format_tier": _format_vertical_tier,
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

    @app.get("/scorecard", response_class=HTMLResponse)
    def scorecard(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        rows = queries.fetch_station_scorecard(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "scorecard.html",
            {
                "rows": rows,
                "format_status": _format_status,
                "format_recommendation": _format_recommendation,
            },
        )

    @app.get("/keywords/hits", response_class=HTMLResponse)
    def keyword_hits(request: Request, days: int = 7) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        window_days = max(1, min(days, 30))
        hits = queries.fetch_keyword_hits(resolved_db, window_days=window_days)
        return TEMPLATES.TemplateResponse(
            request,
            "keyword_hits.html",
            {
                "hits": hits,
                "window_days": window_days,
                "format_ts": _format_ts,
            },
        )

    @app.get("/ops/watchdog", response_class=HTMLResponse)
    def ops_watchdog(request: Request, restarted: str | None = None) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        return TEMPLATES.TemplateResponse(
            request,
            "ops/watchdog.html",
            {
                "overview": queries.fetch_watchdog_overview(resolved_db),
                "restarted_station": restarted,
                "format_ts": _format_ts,
                "format_age": _format_age,
                "format_watchdog_state": _format_watchdog_state,
            },
        )

    @app.get("/verticals", response_class=HTMLResponse)
    @app.get("/novelty", response_class=HTMLResponse)
    @app.get("/novelty/new", response_class=HTMLResponse)
    @app.get("/novelty/known", response_class=HTMLResponse)
    @app.get("/novelty/noise", response_class=HTMLResponse)
    @app.get("/opportunities", response_class=HTMLResponse)
    @app.get("/opportunities/digest-preview", response_class=HTMLResponse)
    @app.get("/opportunities/batch-review", response_class=HTMLResponse)
    @app.get("/sources/landing-pages", response_class=HTMLResponse)
    @app.get("/novelty/known-pending", response_class=HTMLResponse)
    @app.get("/advertisers/opportunities", response_class=HTMLResponse)
    @app.get("/keywords/trademark", response_class=HTMLResponse)
    def owner_review_placeholder(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        return TEMPLATES.TemplateResponse(
            request,
            "owner_review_placeholder.html",
            {"path": request.url.path},
        )

    @app.get("/keywords", response_class=HTMLResponse)
    def keywords_page(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        stations, keywords, matrix = queries.fetch_keyword_matrix(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "keywords.html",
            {"stations": stations, "keywords": keywords, "matrix": matrix},
        )

    @app.get("/review", response_class=HTMLResponse)
    def review_inbox(request: Request, tier: str | None = None, days: int = 7) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        window_days = max(1, min(days, 30))
        rows = queries.fetch_review_inbox(resolved_db, window_days=window_days, tier=tier)
        tier_filter = tier.upper() if tier else None
        if tier_filter not in {None, "A", "B", "C"}:
            tier_filter = None
        return TEMPLATES.TemplateResponse(
            request,
            "review.html",
            {
                "rows": rows,
                "window_days": window_days,
                "tier_filter": tier_filter,
                "format_ts": _format_ts,
                "format_tier": _format_tier,
            },
        )

    @app.get("/cfpb", response_class=HTMLResponse)
    def cfpb_overview(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        overview = queries.fetch_cfpb_overview(resolved_db)
        entities = queries.fetch_cfpb_entities(resolved_db, limit=10)
        candidates = queries.fetch_cfpb_candidates(resolved_db, limit=10, min_score=50)
        return TEMPLATES.TemplateResponse(
            request,
            "cfpb/index.html",
            {
                "overview": overview,
                "top_entities": entities,
                "top_candidates": candidates,
            },
        )

    @app.get("/cfpb/runs", response_class=HTMLResponse)
    def cfpb_runs(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        runs = queries.fetch_cfpb_runs(resolved_db)
        return TEMPLATES.TemplateResponse(request, "cfpb/runs.html", {"runs": runs})

    @app.get("/cfpb/entities", response_class=HTMLResponse)
    def cfpb_entities(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        entities = queries.fetch_cfpb_entities(resolved_db, limit=200)
        return TEMPLATES.TemplateResponse(request, "cfpb/entities.html", {"entities": entities})

    @app.get("/cfpb/candidates", response_class=HTMLResponse)
    def cfpb_candidates(request: Request, min_score: float | None = None) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        candidates = queries.fetch_cfpb_candidates(resolved_db, limit=500, min_score=min_score)
        return TEMPLATES.TemplateResponse(
            request,
            "cfpb/candidates.html",
            {"candidates": candidates, "min_score": min_score},
        )

    @app.get("/cfpb/candidates/{candidate_id}", response_class=HTMLResponse)
    def cfpb_candidate_detail(request: Request, candidate_id: int) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        candidate = queries.fetch_cfpb_candidate_detail(resolved_db, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return TEMPLATES.TemplateResponse(
            request,
            "cfpb/candidate_detail.html",
            {"candidate": candidate},
        )

    @app.post("/cfpb/candidates/{candidate_id}/status")
    def cfpb_candidate_status(
        candidate_id: int,
        status: str = Form(...),
    ) -> RedirectResponse:
        if not queries.update_cfpb_candidate_status(resolved_db, candidate_id, status):
            raise HTTPException(status_code=400, detail="Invalid status update")
        return RedirectResponse(url=f"/cfpb/candidates/{candidate_id}", status_code=303)

    @app.post("/cfpb/entities/{entity_id}/status")
    def cfpb_entity_status(
        entity_id: int,
        status: str = Form(...),
    ) -> RedirectResponse:
        if not queries.update_cfpb_entity_status(resolved_db, entity_id, status):
            raise HTTPException(status_code=400, detail="Invalid status update")
        return RedirectResponse(url="/cfpb/entities", status_code=303)

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


def _format_recommendation(recommendation: str) -> str:
    labels = {
        "keep": ("Keep", "ok"),
        "swap": ("Swap", "err"),
        "fix": ("Fix ingest", "warn"),
        "review": ("Review", "warn"),
        "bench": ("Bench", "muted"),
    }
    label, css = labels.get(recommendation, (recommendation.title(), "muted"))
    return f'<span class="badge {css}">{label}</span>'


def _format_tier(tier: str) -> str:
    labels = {
        "A": ("ระดับ A · คีย์เวิร์ด + โฆษณา", "ok"),
        "B": ("ระดับ B · โฆษณาเท่านั้น", "warn"),
        "C": ("ระดับ C · คีย์เวิร์ดเท่านั้น", "muted"),
    }
    label, css = labels.get(tier, (tier, "muted"))
    return f'<span class="badge {css}">{label}</span>'


def _format_vertical_tier(
    tier: str, *, hit_count: int = 0, no_hit_ok: bool = False
) -> str:
    label = tier.replace("_", " ").title() if tier else "Active"
    return f'<span class="badge muted">{label}</span>'


def _format_watchdog_state(state: str) -> str:
    labels = {
        "healthy": ("ปกติ", "ok"),
        "stale": ("ช้า", "warn"),
        "recovering": ("กำลังกู้คืน", "warn"),
        "failed": ("ล้มเหลว", "err"),
        "disabled": ("ปิด", "muted"),
        "standby": ("พัก", "muted"),
        "unknown": ("ไม่ทราบ", "muted"),
    }
    label, css = labels.get(state, (state.replace("_", " ").title(), "muted"))
    return f'<span class="badge {css}">{label}</span>'
