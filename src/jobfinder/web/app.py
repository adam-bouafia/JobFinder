"""FastAPI web UI: job search (search box + filters + results) and a
standalone company-sponsor lookup.

Mirrors what the CLI already does (`jf list-jobs`, `jf match`, `jf export-
jobs`) as a browser UI, reusing the same functions rather than duplicating
logic. Runs locally via `jf serve`; see docs/architecture.md for the
hosting decision (local-first by default).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db
from ..jobs.export import to_markdown, to_pdf_bytes, to_text
from ..jobs.ingest import StoredJob, list_jobs
from ..paths import DB_PATH
from ..sponsors.match import match_company

EXPORT_MEDIA_TYPES = {
    "md": "text/markdown",
    "txt": "text/plain",
    "pdf": "application/pdf",
}

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def get_db_path() -> Path:
    """FastAPI dependency, overridden in tests to point at a tmp_path DB.

    Keeps the same explicit-db_path testability principle the rest of the
    codebase uses, via FastAPI's own override mechanism instead of
    monkeypatching a global.
    """
    return DB_PATH


def create_app() -> FastAPI:
    app = FastAPI(title="JobFinder")
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def _search_jobs(
        db_path: Path,
        query: str,
        sponsors_only: bool,
        open_applications_only: bool,
        experience: str,
    ) -> list[StoredJob]:
        return list_jobs(
            db_path=db_path,
            query=query or None,
            sponsors_only=sponsors_only,
            open_applications_only=open_applications_only,
            experience_level=experience or None,
            limit=100,
        )

    @app.get("/", response_class=HTMLResponse)
    def index(
        request: Request,
        db_path: Annotated[Path, Depends(get_db_path)],
        query: str = Query(default=""),
        sponsors_only: bool = Query(default=False),
        open_applications_only: bool = Query(default=False),
        experience: str = Query(default=""),
    ) -> HTMLResponse:
        stats = db.sponsor_stats(db_path)
        jobs = _search_jobs(db_path, query, sponsors_only, open_applications_only, experience)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "stats": stats,
                "jobs": jobs,
                "query": query,
                "sponsors_only": sponsors_only,
                "open_applications_only": open_applications_only,
                "experience": experience,
                "active_nav": "home",
            },
        )

    @app.get("/results", response_class=HTMLResponse)
    def results(
        request: Request,
        db_path: Annotated[Path, Depends(get_db_path)],
        query: str = Query(default=""),
        sponsors_only: bool = Query(default=False),
        open_applications_only: bool = Query(default=False),
        experience: str = Query(default=""),
    ) -> HTMLResponse:
        """htmx partial: just the results fragment, for live search/filtering."""
        jobs = _search_jobs(db_path, query, sponsors_only, open_applications_only, experience)
        return templates.TemplateResponse(
            request,
            "_job_results.html",
            {
                "jobs": jobs,
                "query": query,
                "sponsors_only": sponsors_only,
                "open_applications_only": open_applications_only,
                "experience": experience,
            },
        )

    @app.get("/company", response_class=HTMLResponse)
    def company(request: Request, db_path: Annotated[Path, Depends(get_db_path)]) -> HTMLResponse:
        stats = db.sponsor_stats(db_path)
        return templates.TemplateResponse(
            request, "company.html", {"stats": stats, "active_nav": "company"}
        )

    @app.get("/search", response_class=HTMLResponse)
    def search(
        request: Request,
        db_path: Annotated[Path, Depends(get_db_path)],
        company: str = Query(default=""),
    ) -> HTMLResponse:
        company = company.strip()
        if not company:
            return templates.TemplateResponse(
                request, "_match_result.html", {"result": None, "query": ""}
            )
        try:
            result = match_company(company, db_path=db_path)
        except RuntimeError:
            result = None
        return templates.TemplateResponse(
            request, "_match_result.html", {"result": result, "query": company}
        )

    @app.get("/export")
    def export(
        db_path: Annotated[Path, Depends(get_db_path)],
        fmt: str = Query(default="md", alias="format"),
        query: str = Query(default=""),
        sponsors_only: bool = Query(default=False),
        open_applications_only: bool = Query(default=False),
        experience: str = Query(default=""),
    ) -> Response:
        if fmt not in EXPORT_MEDIA_TYPES:
            raise HTTPException(status_code=400, detail="format must be md, txt, or pdf")

        jobs = list_jobs(
            db_path=db_path,
            query=query or None,
            sponsors_only=sponsors_only,
            open_applications_only=open_applications_only,
            experience_level=experience or None,
            limit=500,
        )
        if fmt == "md":
            content: bytes = to_markdown(jobs).encode("utf-8")
        elif fmt == "txt":
            content = to_text(jobs).encode("utf-8")
        else:
            content = to_pdf_bytes(jobs)

        return Response(
            content=content,
            media_type=EXPORT_MEDIA_TYPES[fmt],
            headers={"Content-Disposition": f'attachment; filename="jobfinder-export.{fmt}"'},
        )

    return app


app = create_app()
