"""FastAPI read-only dashboard over SQLite."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard import queries
from shared.config import load_settings
from shared.db import migrate
from shared.metrics import configure_dashboard_metrics, start_metrics_server
from shared.station_control import (
    StationControlCommand,
    enqueue_station_command,
    station_exists,
)

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

    @app.get("/api/health")
    def api_health() -> JSONResponse:
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
                "format_tier": _format_vertical_tier,
            },
        )

    @app.get("/verticals", response_class=HTMLResponse)
    def verticals_index(request: Request, days: int = 7) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        window_days = max(1, min(days, 30))
        summaries = queries.fetch_vertical_summaries(resolved_db, window_days=window_days)
        queue = queries.fetch_queue_health(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "verticals.html",
            {
                "summaries": summaries,
                "window_days": window_days,
                "queue": queue,
                "format_ts": _format_ts,
                "format_tier": _format_vertical_tier,
            },
        )

    @app.get("/verticals/{vertical_slug}", response_class=HTMLResponse)
    def vertical_detail(request: Request, vertical_slug: str, days: int = 7) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        from shared.verticals import vertical_id_from_slug

        vertical_id = vertical_id_from_slug(vertical_slug)
        window_days = max(1, min(days, 30))
        summary, hits, opportunities = queries.fetch_vertical_detail(
            resolved_db, vertical_id, window_days=window_days
        )
        if summary is None:
            raise HTTPException(status_code=404, detail="Vertical not found")
        return TEMPLATES.TemplateResponse(
            request,
            "vertical_detail.html",
            {
                "summary": summary,
                "hits": hits,
                "opportunities": opportunities,
                "vertical_slug": vertical_slug,
                "window_days": window_days,
                "format_ts": _format_ts,
                "format_tier": _format_vertical_tier,
            },
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

    @app.get("/advertisers/opportunities", response_class=HTMLResponse)
    def advertisers_opportunities(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.advertiser_entities_available(resolved_db):
            migrate(resolved_db)
        rows = queries.fetch_hit_advertisers(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "advertisers/opportunities.html",
            {"rows": rows, "format_ts": _format_ts},
        )

    @app.get("/advertisers/opportunities/{advertiser_id}", response_class=HTMLResponse)
    def advertiser_opportunity_detail(request: Request, advertiser_id: int) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        summary, detections = queries.fetch_hit_advertiser_detail(resolved_db, advertiser_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="Advertiser not found")
        return TEMPLATES.TemplateResponse(
            request,
            "advertisers/detail.html",
            {
                "advertiser": summary,
                "detections": detections,
                "format_ts": _format_ts,
            },
        )

    @app.get("/keywords/trademark", response_class=HTMLResponse)
    def trademark_keywords(request: Request, source: str | None = None) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        rows = queries.fetch_trademark_keywords(
            resolved_db,
            source_type=source,
            status="new",
        )
        return TEMPLATES.TemplateResponse(
            request,
            "keywords/trademark.html",
            {"rows": rows, "source_filter": source, "format_ts": _format_ts},
        )

    @app.get("/cfpb", response_class=HTMLResponse)
    def cfpb_index(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.cfpb_tables_available(resolved_db):
            return _cfpb_unavailable(request)
        stats = queries.fetch_cfpb_overview(resolved_db)
        return TEMPLATES.TemplateResponse(request, "cfpb/index.html", {"stats": stats})

    @app.get("/cfpb/candidates", response_class=HTMLResponse)
    def cfpb_candidates(request: Request, min_score: float = 0.0) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.cfpb_tables_available(resolved_db):
            return _cfpb_unavailable(request)
        rows = queries.fetch_cfpb_candidates(resolved_db, min_score=min_score)
        return TEMPLATES.TemplateResponse(
            request,
            "cfpb/candidates.html",
            {"rows": rows, "min_score": min_score, "format_cfpb_status": _format_cfpb_status},
        )

    @app.get("/cfpb/candidates/{candidate_id}", response_class=HTMLResponse)
    def cfpb_candidate_detail(request: Request, candidate_id: int) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.cfpb_tables_available(resolved_db):
            return _cfpb_unavailable(request)
        row = queries.fetch_cfpb_candidate_detail(resolved_db, candidate_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return TEMPLATES.TemplateResponse(
            request,
            "cfpb/candidate_detail.html",
            {"row": row, "format_cfpb_status": _format_cfpb_status},
        )

    @app.get("/cfpb/entities", response_class=HTMLResponse)
    def cfpb_entities(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.cfpb_tables_available(resolved_db):
            return _cfpb_unavailable(request)
        rows = queries.fetch_cfpb_entities(resolved_db)
        return TEMPLATES.TemplateResponse(request, "cfpb/entities.html", {"rows": rows})

    @app.get("/cfpb/runs", response_class=HTMLResponse)
    def cfpb_runs(request: Request) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.cfpb_tables_available(resolved_db):
            return _cfpb_unavailable(request)
        rows = queries.fetch_cfpb_runs(resolved_db)
        return TEMPLATES.TemplateResponse(request, "cfpb/runs.html", {"rows": rows})

    @app.get("/ops/watchdog", response_class=HTMLResponse)
    def ops_watchdog(request: Request, restarted: str | None = None) -> HTMLResponse:
        if not queries.db_exists(resolved_db):
            return _no_database(request)
        if not queries.watchdog_tables_available(resolved_db):
            migrate(resolved_db)
        overview = queries.fetch_watchdog_overview(resolved_db)
        return TEMPLATES.TemplateResponse(
            request,
            "ops/watchdog.html",
            {
                "overview": overview,
                "restarted_station": restarted,
                "format_ts": _format_ts,
                "format_age": _format_age,
                "format_watchdog_state": _format_watchdog_state,
            },
        )

    @app.post("/ops/watchdog/restart/{station_id}")
    def ops_watchdog_restart(station_id: str) -> RedirectResponse:
        if not queries.db_exists(resolved_db):
            raise HTTPException(status_code=503, detail="Database not available")
        if not station_exists(resolved_db, station_id):
            raise HTTPException(status_code=404, detail="Station not found")
        if not queries.control_commands_available(resolved_db):
            migrate(resolved_db)
        enqueue_station_command(
            resolved_db,
            station_id=station_id,
            command=StationControlCommand.RESTART,
            reason="dashboard manual restart",
        )
        return RedirectResponse(
            url=f"/ops/watchdog?restarted={station_id}",
            status_code=303,
        )

    app.state.db_path = resolved_db

    from dashboard.routes.harvest import create_harvest_router
    from dashboard.routes.hermes import create_hermes_router
    from dashboard.routes.memory import create_memory_router
    from dashboard.routes.novelty import create_novelty_router
    from dashboard.routes.radiosense import create_radiosense_router
    from dashboard.routes.system import create_system_router

    app.include_router(create_memory_router())
    app.include_router(create_radiosense_router(resolved_db))
    app.include_router(
        create_harvest_router(
            resolved_db,
            format_ts=_format_ts,
            no_database_handler=_no_database,
        )
    )
    app.include_router(create_system_router(resolved_db))
    app.include_router(create_hermes_router())
    app.include_router(
        create_novelty_router(
            resolved_db,
            format_ts=_format_ts,
            no_database_handler=_no_database,
        )
    )

    return app


def _no_database(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "no_database.html", {}, status_code=200)


def _cfpb_unavailable(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request,
        "cfpb/unavailable.html",
        {},
        status_code=503,
    )


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
        "healthy": ("Healthy", "ok"),
        "degraded": ("Degraded", "warn"),
        "paused": ("Paused", "muted"),
        "backoff": ("Backoff", "warn"),
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
        "A": ("A · kw+ad", "ok"),
        "B": ("B · ad only", "warn"),
        "C": ("C · kw only", "muted"),
    }
    label, css = labels.get(tier, (tier, "muted"))
    return f'<span class="badge {css}">{label}</span>'


def _format_vertical_tier(tier: str, *, hit_count: int = 0, no_hit_ok: bool = False) -> str:
    if tier == "hot":
        label, css = "Hot", "ok"
    elif tier == "watchlist":
        label, css = "Watchlist", "warn"
    elif no_hit_ok and hit_count == 0:
        label, css = "No hits (OK)", "muted"
    elif hit_count == 0:
        label, css = "No hits", "muted"
    else:
        label, css = "Active", "ok"
    return f'<span class="badge {css}">{label}</span>'


def _format_cfpb_status(status: str) -> str:
    labels = {
        "approved_seed": ("Approved seed", "ok"),
        "needs_verification": ("Needs review", "warn"),
        "rejected": ("Rejected", "err"),
        "new": ("New", "muted"),
        "completed": ("Completed", "ok"),
        "failed": ("Failed", "err"),
        "running": ("Running", "warn"),
    }
    label, css = labels.get(status, (status.replace("_", " ").title(), "muted"))
    return f'<span class="badge {css}">{label}</span>'


def _format_watchdog_state(state: str) -> str:
    labels = {
        "healthy": ("Healthy", "ok"),
        "stale": ("Stale", "warn"),
        "recovering": ("Recovering", "warn"),
        "failed": ("Failed", "err"),
        "disabled": ("Disabled", "muted"),
        "standby": ("Standby", "muted"),
        "unknown": ("Unknown", "muted"),
    }
    label, css = labels.get(state, (state.replace("_", " ").title(), "muted"))
    return f'<span class="badge {css}">{label}</span>'
