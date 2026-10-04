"""FastAPI web UI: job search (search box + filters + results) and a
standalone company-sponsor lookup.

Mirrors what the CLI already does (`jf list-jobs`, `jf match`, `jf export-
jobs`) as a browser UI, reusing the same functions rather than duplicating
logic. Runs locally via `jf serve`; see docs/architecture.md for the
hosting decision (local-first by default).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db
from ..jobs.export import to_markdown, to_pdf_bytes, to_text
from ..jobs.ingest import StoredJob, count_jobs, distinct_cities, list_jobs, reindex_all_jobs
from ..matching.score import rescore_jobs
from ..paths import RESUME_DIR
from ..resume.parse import latest_resume_profile, parse_resume
from ..search import meilisearch_client
from ..sponsors.match import match_company

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

EXPORT_MEDIA_TYPES = {
    "md": "text/markdown",
    "txt": "text/plain",
    "pdf": "application/pdf",
}

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def get_dsn() -> str | None:
    """FastAPI dependency, overridden in tests to point at a throwaway
    Postgres schema.

    Keeps the same explicit-dsn testability principle the rest of the
    codebase uses, via FastAPI's own override mechanism instead of
    monkeypatching a global. None means "use the real DATABASE_URL" - see
    db.cursor().
    """
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="JobFinder")
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def _search(
        dsn: str | None,
        query: str,
        city: str,
        sponsors_only: bool,
        open_applications_only: bool,
        experience: str,
    ) -> tuple[list[StoredJob] | list[dict[str, Any]], int]:
        """Ranked, typo-tolerant search via Meilisearch when it's up;
        falls back to a direct Postgres query otherwise. The CLI and
        /export always use Postgres directly (list_jobs/count_jobs) - the
        search index is an enhancement over the source of truth, never a
        single point of failure for the whole tool."""
        try:
            return meilisearch_client.search_jobs(
                query=query or None,
                city=city or None,
                sponsors_only=sponsors_only,
                open_applications_only=open_applications_only,
                experience_level=experience or None,
                limit=100,
            )
        except Exception:
            # Self-heal: a self-hosted Meilisearch with no persistent
            # storage loses its index on every container restart (see
            # deploy/modal_app.py) - confirmed live that it can then sit
            # silently empty indefinitely, since this fallback is
            # deliberately quiet. Push everything back in now so the
            # *next* search is back on the real index, not just this one
            # falling back. reindex_all_jobs() never raises.
            reindex_all_jobs(dsn)
            jobs = list_jobs(
                dsn=dsn,
                query=query or None,
                city=city or None,
                sponsors_only=sponsors_only,
                open_applications_only=open_applications_only,
                experience_level=experience or None,
                limit=100,
            )
            total = count_jobs(
                dsn=dsn,
                query=query or None,
                city=city or None,
                sponsors_only=sponsors_only,
                open_applications_only=open_applications_only,
                experience_level=experience or None,
            )
            return jobs, total

    @app.get("/", response_class=HTMLResponse)
    def index(
        request: Request,
        dsn: Annotated[str | None, Depends(get_dsn)],
        query: str = Query(default=""),
        city: str = Query(default=""),
        sponsors_only: bool = Query(default=False),
        open_applications_only: bool = Query(default=False),
        experience: str = Query(default=""),
        uploaded: bool = Query(default=False),
        error: str = Query(default=""),
    ) -> HTMLResponse:
        stats = db.sponsor_stats(dsn)
        jobs, total = _search(dsn, query, city, sponsors_only, open_applications_only, experience)
        resume_profile = latest_resume_profile(dsn)
        cities = distinct_cities(dsn)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "stats": stats,
                "jobs": jobs,
                "total": total,
                "query": query,
                "city": city,
                "cities": cities,
                "sponsors_only": sponsors_only,
                "open_applications_only": open_applications_only,
                "experience": experience,
                "uploaded": uploaded,
                "error": error,
                "resume_profile": resume_profile,
                "active_nav": "home",
            },
        )

    @app.get("/results", response_class=HTMLResponse)
    def results(
        request: Request,
        dsn: Annotated[str | None, Depends(get_dsn)],
        query: str = Query(default=""),
        city: str = Query(default=""),
        sponsors_only: bool = Query(default=False),
        open_applications_only: bool = Query(default=False),
        experience: str = Query(default=""),
    ) -> HTMLResponse:
        """htmx partial: just the results fragment, for live filtering as
        you type."""
        jobs, total = _search(dsn, query, city, sponsors_only, open_applications_only, experience)
        return templates.TemplateResponse(
            request,
            "_job_results.html",
            {
                "jobs": jobs,
                "total": total,
                "query": query,
                "city": city,
                "sponsors_only": sponsors_only,
                "open_applications_only": open_applications_only,
                "experience": experience,
            },
        )

    @app.get("/company", response_class=HTMLResponse)
    def company(request: Request, dsn: Annotated[str | None, Depends(get_dsn)]) -> HTMLResponse:
        stats = db.sponsor_stats(dsn)
        return templates.TemplateResponse(
            request, "company.html", {"stats": stats, "active_nav": "company"}
        )

    @app.post("/resume/upload")
    def upload_resume(
        dsn: Annotated[str | None, Depends(get_dsn)],
        file: UploadFile,
    ) -> RedirectResponse:
        looks_like_pdf = file.content_type == "application/pdf" or (
            file.filename or ""
        ).lower().endswith(".pdf")
        if not looks_like_pdf:
            params = urlencode({"error": "Only PDF resumes are supported."})
            return RedirectResponse(url=f"/?{params}", status_code=303)

        RESUME_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = _SAFE_FILENAME.sub("_", file.filename or "resume.pdf")
        dest = RESUME_DIR / f"{int(time.time())}-{safe_name}"
        dest.write_bytes(file.file.read())

        try:
            parse_resume(dest, dsn=dsn)
        except Exception:
            params = urlencode(
                {"error": "Could not read that PDF - is it a text or scanned resume?"}
            )
            return RedirectResponse(url=f"/?{params}", status_code=303)
        rescore_jobs(dsn=dsn)

        return RedirectResponse(url="/?uploaded=true", status_code=303)

    @app.get("/search", response_class=HTMLResponse)
    def search(
        request: Request,
        dsn: Annotated[str | None, Depends(get_dsn)],
        company: str = Query(default=""),
    ) -> HTMLResponse:
        company = company.strip()
        if not company:
            return templates.TemplateResponse(
                request, "_match_result.html", {"result": None, "query": ""}
            )
        try:
            result = match_company(company, dsn=dsn)
        except RuntimeError:
            result = None
        return templates.TemplateResponse(
            request, "_match_result.html", {"result": result, "query": company}
        )

    @app.get("/export")
    def export(
        dsn: Annotated[str | None, Depends(get_dsn)],
        fmt: str = Query(default="md", alias="format"),
        query: str = Query(default=""),
        city: str = Query(default=""),
        sponsors_only: bool = Query(default=False),
        open_applications_only: bool = Query(default=False),
        experience: str = Query(default=""),
    ) -> Response:
        if fmt not in EXPORT_MEDIA_TYPES:
            raise HTTPException(status_code=400, detail="format must be md, txt, or pdf")

        jobs = list_jobs(
            dsn=dsn,
            query=query or None,
            city=city or None,
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
