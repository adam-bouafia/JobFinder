"""jf -- JobFinder CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from .jobs import adzuna as jobs_adzuna
from .jobs.ats import ATS_FETCHERS
from .jobs.ats import fetch as ats_fetch
from .jobs.export import export_jobs
from .jobs.ingest import ingest_jobs, list_jobs
from .matching.score import rescore_jobs
from .paths import PROJECT_ROOT
from .resume.parse import parse_resume
from .sponsors import export as sponsors_export
from .sponsors import scrape as sponsors_scrape
from .sponsors.match import match_company

# Explicit path, not dotenv's default cwd-upward search: `jf` should pick
# up repo-root secrets (e.g. ADZUNA_APP_ID/KEY) regardless of where it's
# run from.
load_dotenv(PROJECT_ROOT / ".env")

app = typer.Typer(
    help="Personal NL job-search tool: IND sponsor lookup and job matching.",
    no_args_is_help=True,
)
console = Console()


@app.command("sync-sponsors")
def cmd_sync_sponsors() -> None:
    """Fetch the IND recognised-sponsors register and refresh the local copy."""
    count = sponsors_scrape.sync_sponsors()
    console.print(f"[green]Synced {count} sponsors from IND.[/green]")
    snapshot_count = sponsors_export.export_snapshot()
    console.print(f"[green]Wrote snapshot with {snapshot_count} sponsors.[/green]")


@app.command("match")
def cmd_match(
    company: str = typer.Option(..., "--company", help="Company name to check."),
    threshold: float = typer.Option(90.0, help="Minimum fuzzy-match score (0-100)."),
) -> None:
    """Check whether a company is an IND recognised sponsor."""
    result = match_company(company, threshold=threshold)
    if result.is_sponsor:
        console.print(
            f"[green]Recognised sponsor[/green]: {result.matched_name} "
            f"(KVK {result.kvk}, score {result.score:.1f})"
        )
    else:
        console.print(f"[yellow]Not found[/yellow] (best score {result.score:.1f})")


@app.command("parse-resume")
def cmd_parse_resume(
    path: Path = typer.Argument(..., exists=True, readable=True, help="Path to a resume PDF."),
) -> None:
    """Extract skills, experience, and education from a resume PDF."""
    profile = parse_resume(path)
    console.print(f"[green]Parsed {path}[/green]")
    console.print(f"Skills: {', '.join(profile.skills) or '(none detected)'}")
    years = f"{profile.years_experience:.0f}" if profile.years_experience is not None else "?"
    console.print(f"Years of experience (heuristic): {years}")
    if profile.education:
        console.print("Education:")
        for line in profile.education:
            console.print(f"  - {line}")
    else:
        console.print("Education: (none detected)")


@app.command("fetch-jobs")
def cmd_fetch_jobs(
    source: str = typer.Option(
        ..., "--source", help=f"ATS to fetch from: {', '.join(ATS_FETCHERS)}."
    ),
    slug: str = typer.Option(..., "--slug", help="Company's slug on that ATS."),
) -> None:
    """Fetch a company's open roles from a direct ATS endpoint and store them.

    No automatic discovery of which company uses which ATS/slug (that
    would need scraping career pages to find out, not done here) - pass a
    slug you already know, e.g. from a company's careers page URL.
    """
    if source not in ATS_FETCHERS:
        console.print(f"[red]Unknown source[/red]. Choose from: {', '.join(ATS_FETCHERS)}")
        raise typer.Exit(code=1)
    listings = ats_fetch(source, slug)
    inserted = ingest_jobs(listings)
    console.print(
        f"[green]Fetched {len(listings)} roles from {source}:{slug}, {inserted} new.[/green]"
    )


@app.command("search-jobs")
def cmd_search_jobs(
    query: str = typer.Option(..., "--query", help="Search text, e.g. 'software engineer'."),
    city: str | None = typer.Option(None, help="Narrow to a location, e.g. 'Amsterdam'."),
    country: str = typer.Option("nl", help="Adzuna country code."),
) -> None:
    """Search Adzuna and store the results.

    Needs free credentials: sign up at https://developer.adzuna.com/ and
    set ADZUNA_APP_ID / ADZUNA_APP_KEY.
    """
    try:
        listings = jobs_adzuna.search(query, country=country, where=city)
    except jobs_adzuna.AdzunaCredentialsError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    inserted = ingest_jobs(listings)
    console.print(f"[green]Found {len(listings)} roles, {inserted} new.[/green]")


@app.command("rescore-jobs")
def cmd_rescore_jobs() -> None:
    """Recompute every stored job's fit score against the latest parsed resume."""
    count = rescore_jobs()
    console.print(f"[green]Rescored {count} jobs.[/green]")


@app.command("list-jobs")
def cmd_list_jobs(
    query: str | None = typer.Option(None, "--query", help="Search title/company name."),
    city: str | None = typer.Option(None, help="Filter by location, e.g. 'Amsterdam'."),
    sponsors_only: bool = typer.Option(False, help="Only IND-recognised-sponsor companies."),
    open_applications_only: bool = typer.Option(False, help="Only open/speculative postings."),
    experience: str | None = typer.Option(
        None, help="Filter by experience level: junior, mid, or senior."
    ),
    min_fit: float | None = typer.Option(None, help="Minimum fit score."),
    limit: int = typer.Option(50, help="Max rows to show."),
) -> None:
    """List stored jobs, ranked by fit score."""
    jobs = list_jobs(
        query=query,
        city=city,
        sponsors_only=sponsors_only,
        open_applications_only=open_applications_only,
        experience_level=experience,
        min_fit_score=min_fit,
        limit=limit,
    )
    if not jobs:
        console.print("[yellow]No jobs match.[/yellow]")
        return
    for job in jobs:
        sponsor_tag = "[green]sponsor[/green]" if job.sponsor_kvk else "[dim]unmatched[/dim]"
        open_app_tag = " [cyan]open-application[/cyan]" if job.is_open_application else ""
        level_tag = f" [magenta]{job.experience_level}[/magenta]" if job.experience_level else ""
        fit = f"{job.fit_score:.1f}" if job.fit_score is not None else "?"
        console.print(
            f"[{fit}] {job.company_name} - {job.title} "
            f"({sponsor_tag}){open_app_tag}{level_tag}\n    {job.url}"
        )


@app.command("export-jobs")
def cmd_export_jobs(
    path: Path = typer.Argument(..., help="Output file - .md, .txt, or .pdf."),
    query: str | None = typer.Option(None, "--query", help="Search title/company name."),
    city: str | None = typer.Option(None, help="Filter by location, e.g. 'Amsterdam'."),
    sponsors_only: bool = typer.Option(False, help="Only IND-recognised-sponsor companies."),
    open_applications_only: bool = typer.Option(False, help="Only open/speculative postings."),
    experience: str | None = typer.Option(
        None, help="Filter by experience level: junior, mid, or senior."
    ),
    min_fit: float | None = typer.Option(None, help="Minimum fit score."),
    limit: int = typer.Option(200, help="Max rows to export."),
) -> None:
    """Export stored jobs to Markdown, text, or PDF - format from the extension."""
    jobs = list_jobs(
        query=query,
        city=city,
        sponsors_only=sponsors_only,
        open_applications_only=open_applications_only,
        experience_level=experience,
        min_fit_score=min_fit,
        limit=limit,
    )
    try:
        export_jobs(jobs, path)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Wrote {len(jobs)} jobs to {path}[/green]")


@app.command("serve")
def cmd_serve(
    host: str = typer.Option(
        "127.0.0.1",
        help="Bind address. Only change this if you know "
        "you want it reachable beyond this machine (e.g. over Tailscale).",
    ),
    port: int = typer.Option(8000, help="Port to listen on."),
) -> None:
    """Run the local web UI (sponsor status + company lookup)."""
    import uvicorn

    console.print(f"[green]Serving on http://{host}:{port}[/green] (Ctrl+C to stop)")
    uvicorn.run("jobfinder.web.app:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    app()
