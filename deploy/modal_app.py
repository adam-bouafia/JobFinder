"""Modal deployment for the JobFinder web UI.

    uv run modal setup                      # one-time: authenticate the CLI
    uv run modal deploy deploy/modal_app.py  # deploy, prints the live URL
    uv run modal serve deploy/modal_app.py   # temporary preview URL, live reload

Storage is a real networked Postgres (Neon), not SQLite-on-a-Volume
anymore - see docs/architecture.md for why. `DATABASE_URL` comes from the
`jobfinder-db` Modal Secret. The Volume still exists, but only for resume
PDF uploads and the `sponsors_latest.json` snapshot the Chrome extension
bundles - both plain files, nothing shared/mutable the way the old SQLite
file was.

Still pinned to a single container (max_containers=1). That was
originally required (Volume "last write wins" under concurrent SQLite
writers); Postgres removes that specific constraint, so this is now a
deliberate choice to keep things simple for a personal, single-user tool
rather than a hard requirement - revisit if this ever needs real
concurrency.

Known limitation, acceptable at this scale: a long-lived warm container
won't see a monthly sync's new volume writes until it's recycled (Modal
scale-to-zero on idle naturally does this for a low-traffic personal
tool; not worth the complexity of reload-per-request for once-a-month
freshness).

Job data comes only from direct ATS endpoints (Greenhouse/Lever/Ashby/
Recruitee/Workable) via `seed_jobs` - every link shown is the employer's
own posting, never an aggregator redirect. Adzuna was tried and dropped
(see docs/architecture.md's risk table): its API terms require a visible
"Jobs by Adzuna" attribution badge, which conflicts with a clean,
direct-to-employer open-source product. Run `seed_jobs` once manually
after a fresh database (see deploy/README.md) to pull a company's board;
it isn't scheduled, since which companies to track is a deliberate,
manual choice, not something to auto-refresh.
"""

from __future__ import annotations

import modal

app = modal.App("jobfinder")

# Kept in sync with [project.dependencies] in pyproject.toml by
# tests/test_deploy_deps.py, which fails loudly if they drift - not by a
# runtime pyproject.toml read. That was tried first and broke differently:
# Modal re-imports this whole module inside the remote container just to
# look up the function objects, and __file__ resolves to a different
# relative depth there (no local repo checkout) than at local `modal
# deploy` time, so the same path expression crashed one way locally-wrong
# and another way remotely-wrong. A plain hardcoded list has no such
# environment-dependent behaviour; a test is the right place to catch
# drift, not cleverness in code that runs twice in two different places.
RUNTIME_DEPENDENCIES = [
    "typer>=0.12",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "rich>=13.0",
    "rapidfuzz>=3.9",
    "fastapi>=0.142.2",
    "uvicorn[standard]>=0.54.0",
    "jinja2>=3.1.6",
    "pdfplumber>=0.11.10",
    "pytesseract>=0.3.13",
    "pdf2image>=1.17.0",
    "python-dotenv>=1.2.4",
    "reportlab>=5.0.1",
    "python-multipart>=0.0.20",
    "psycopg[binary]>=3.2",
    "psycopg-pool>=3.2",
]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("tesseract-ocr", "poppler-utils")  # OCR fallback + pdf2image, same as local
    .uv_pip_install(*RUNTIME_DEPENDENCIES)
    # add_local_python_source only copies .py files - the web UI's
    # templates/ and static/ (non-Python package data) silently went
    # missing with it, crash-looping every request on StaticFiles'
    # eager directory check. add_local_dir copies the real directory tree.
    .add_local_dir("src/jobfinder", remote_path="/root/jobfinder")
)

volume = modal.Volume.from_name("jobfinder-data", create_if_missing=True)
DATA_MOUNT = "/data"


DB_SECRET = modal.Secret.from_name("jobfinder-db")


@app.function(
    image=image,
    volumes={DATA_MOUNT: volume},
    secrets=[DB_SECRET],
    max_containers=1,
    timeout=60,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app(label="jobfinder")  # https://<workspace>--jobfinder.modal.run, not -web
def web():  # type: ignore[no-untyped-def]  # Modal's own decorator, not typed for strict mypy
    import os

    os.environ["JOBFINDER_DATA_DIR"] = DATA_MOUNT
    from jobfinder.web.app import app as fastapi_app

    return fastapi_app


@app.function(
    image=image,
    volumes={DATA_MOUNT: volume},
    secrets=[DB_SECRET],
    schedule=modal.Cron("0 9 1 * *"),  # 1st of the month - matches IND's own cadence
    timeout=300,
)
def sync_sponsors() -> None:
    """Mirrors `jf sync-sponsors`, for the deployed instance's Postgres."""
    import os

    os.environ["JOBFINDER_DATA_DIR"] = DATA_MOUNT
    from jobfinder.sponsors import export as sponsors_export
    from jobfinder.sponsors import scrape as sponsors_scrape

    count = sponsors_scrape.sync_sponsors()
    sponsors_export.export_snapshot()
    volume.commit()
    print(f"Synced {count} sponsors")


@app.function(
    image=image,
    secrets=[DB_SECRET],
    timeout=300,
)
def seed_jobs(source: str = "greenhouse", slug: str = "stripe") -> None:
    """Mirrors `jf fetch-jobs` + `jf rescore-jobs`, for the deployed
    instance's Postgres. Not scheduled - run manually (see
    deploy/README.md) to add or top up a company's roles on the live site.
    No Volume needed here: this only ever writes to Postgres.
    """
    from jobfinder.jobs.ats import fetch as ats_fetch
    from jobfinder.jobs.ingest import ingest_jobs
    from jobfinder.matching.score import rescore_jobs

    listings = ats_fetch(source, slug)
    inserted = ingest_jobs(listings)
    rescored = rescore_jobs()
    print(f"Found {len(listings)} roles, {inserted} new, {rescored} rescored")
