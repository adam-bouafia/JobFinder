"""jf -- JobFinder CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .resume.parse import parse_resume
from .sponsors import export as sponsors_export
from .sponsors import scrape as sponsors_scrape
from .sponsors.match import match_company

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
