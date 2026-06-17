"""Novelty-first keyword discovery dashboard routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from alerter.novelty_reporter import fetch_pending_opportunities, format_pending_digest
from dashboard import novelty_queries, queries
from worker import novelty_review

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _safe_redirect(path: str, default: str) -> str:
    if path.startswith("/") and not path.startswith("//"):
        return path
    return default


def create_novelty_router(
    db_path: Path,
    *,
    format_ts,
    no_database_handler,
) -> APIRouter:
    router = APIRouter()

    def _context_base() -> dict[str, object]:
        return {"format_ts": format_ts}

    @router.get("/novelty", response_class=HTMLResponse)
    def novelty_index(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        overview = novelty_queries.fetch_novelty_overview(db_path)
        recent = novelty_queries.fetch_novelty_results(db_path, limit=25)
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/index.html",
            {**_context_base(), "overview": overview, "recent": recent, "redirect": "/novelty"},
        )

    @router.get("/novelty/new", response_class=HTMLResponse)
    def novelty_new(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        rows = novelty_queries.fetch_novelty_results(db_path, status_filter="new")
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/new.html",
            {**_context_base(), "rows": rows, "title": "New candidates", "redirect": "/novelty/new"},
        )

    @router.get("/novelty/known", response_class=HTMLResponse)
    def novelty_known(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        rows = novelty_queries.fetch_novelty_results(db_path, status_filter="known")
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/known.html",
            {**_context_base(), "rows": rows, "title": "Known / generic (dashboard only)", "redirect": "/novelty/known"},
        )

    @router.get("/novelty/noise", response_class=HTMLResponse)
    def novelty_noise(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        rows = novelty_queries.fetch_novelty_results(db_path, status_filter="noise")
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/noise.html",
            {**_context_base(), "rows": rows, "title": "Noise / excluded / weak evidence", "redirect": "/novelty/noise"},
        )

    @router.get("/sources/landing-pages", response_class=HTMLResponse)
    def landing_pages_source(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        view = novelty_queries.fetch_landing_page_source_view(db_path)
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/landing_pages.html",
            {**_context_base(), "view": view},
        )

    @router.get("/novelty/known-pending", response_class=HTMLResponse)
    def novelty_known_pending(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        rows = novelty_queries.fetch_known_terms_pending(db_path)
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/known_pending.html",
            {**_context_base(), "rows": rows},
        )

    @router.post("/novelty/{novelty_result_id}/mark-noise")
    def novelty_mark_noise(
        novelty_result_id: int,
        redirect: str = Form("/novelty"),
    ) -> RedirectResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        novelty_review.mark_noise(db_path, novelty_result_id=novelty_result_id)
        return RedirectResponse(url=_safe_redirect(redirect, "/novelty"), status_code=303)

    @router.post("/novelty/{novelty_result_id}/add-to-known")
    def novelty_add_to_known(
        novelty_result_id: int,
        term_type: str = Form("generic_keyword"),
        redirect: str = Form("/novelty/known-pending"),
    ) -> RedirectResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        detail = novelty_queries.fetch_novelty_result_detail(db_path, novelty_result_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Novelty result not found")
        candidate_text, _candidate_type, vertical, candidate_id = detail
        if term_type not in {"brand", "generic_keyword"}:
            term_type = "generic_keyword"
        novelty_review.add_to_known_pending(
            db_path,
            candidate_text,
            term_type,
            vertical,
            candidate_id,
        )
        return RedirectResponse(
            url=_safe_redirect(redirect, "/novelty/known-pending"),
            status_code=303,
        )

    @router.get("/opportunities/batch-review", response_class=HTMLResponse)
    def opportunities_batch_review(request: Request, batch_id: str | None = None) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        review = novelty_queries.fetch_batch_review(db_path, batch_id=batch_id)
        top_opportunities = sorted(
            review.report_eligible_rows,
            key=lambda row: (row.opportunity_score, row.novelty_score),
            reverse=True,
        )[:10]
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/batch_review.html",
            {
                **_context_base(),
                "review": review,
                "top_opportunities": top_opportunities,
                "redirect": "/opportunities/batch-review",
            },
        )

    @router.get("/opportunities/digest-preview", response_class=HTMLResponse)
    def opportunities_digest_preview(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        digest = format_pending_digest(db_path)
        pending_count = len(fetch_pending_opportunities(db_path, limit=1000))
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/digest_preview.html",
            {
                **_context_base(),
                "digest": digest,
                "pending_count": pending_count,
            },
        )

    @router.get("/opportunities", response_class=HTMLResponse)
    def opportunities(request: Request) -> HTMLResponse:
        if not queries.db_exists(db_path):
            return no_database_handler(request)
        rows = novelty_queries.fetch_keyword_opportunities(db_path)
        return TEMPLATES.TemplateResponse(
            request,
            "novelty/opportunities.html",
            {**_context_base(), "rows": rows, "title": "Report-eligible opportunities", "redirect": "/opportunities"},
        )

    @router.post("/opportunities/{opportunity_id}/approve")
    def opportunity_approve(
        opportunity_id: int,
        redirect: str = Form("/opportunities"),
    ) -> RedirectResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        try:
            novelty_review.approve_opportunity(db_path, opportunity_id)
        except novelty_review.ReviewError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RedirectResponse(url=_safe_redirect(redirect, "/opportunities"), status_code=303)

    @router.post("/opportunities/{opportunity_id}/reject")
    def opportunity_reject(
        opportunity_id: int,
        redirect: str = Form("/opportunities"),
    ) -> RedirectResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        try:
            novelty_review.reject_opportunity(db_path, opportunity_id)
        except novelty_review.ReviewError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RedirectResponse(url=_safe_redirect(redirect, "/opportunities"), status_code=303)

    @router.post("/opportunities/{opportunity_id}/archive")
    def opportunity_archive(
        opportunity_id: int,
        redirect: str = Form("/opportunities"),
    ) -> RedirectResponse:
        if not queries.db_exists(db_path):
            raise HTTPException(status_code=503, detail="Database not available")
        try:
            novelty_review.archive_item(db_path, "opportunity", opportunity_id)
        except novelty_review.ReviewError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RedirectResponse(url=_safe_redirect(redirect, "/opportunities"), status_code=303)

    return router
