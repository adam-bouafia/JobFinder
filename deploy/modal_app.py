"""Modal deployment for the JobFinder web UI.

    uv run modal setup                      # one-time: authenticate the CLI
    uv run modal deploy deploy/modal_app.py  # deploy, prints the live URL
    uv run modal serve deploy/modal_app.py   # temporary preview URL, live reload

A persistent Volume holds the data directory (SQLite DB + sponsor
snapshot) so it survives across deploys and container restarts - same
file, same WAL-mode SQLite, as running locally.

Deliberately pinned to a single container (max_containers=1): Modal
Volumes use "last write wins" semantics under concurrent writes from
multiple containers, which would risk corrupting the SQLite file. One
container handling several requests concurrently (@modal.concurrent) is
the right trade for a personal, single-user tool - real horizontal
scaling would need a proper networked database instead, not this.

Known limitation, acceptable at this scale: a long-lived warm container
won't see a monthly sync's new volume writes until it's recycled (Modal
scale-to-zero on idle naturally does this for a low-traffic personal
tool; not worth the complexity of reload-per-request for once-a-month
freshness).

Job search (Adzuna) runs here too, via `seed_jobs` and via the web UI's
own "Fetch new roles" form - both read the `jobfinder-adzuna` Modal
Secret (ADZUNA_APP_ID/ADZUNA_APP_KEY) and write into this same volume.
Run `seed_jobs` once manually after a fresh volume (see deploy/README.md);
it isn't scheduled on its own, since `sync_sponsors` already covers the
once-a-month cadence this tool actually needs and repeated Adzuna calls
would just re-fetch mostly the same postings - the web form covers
on-demand top-ups instead.
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


@app.function(
    image=image,
    volumes={DATA_MOUNT: volume},
    secrets=[modal.Secret.from_name("jobfinder-adzuna")],
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
    schedule=modal.Cron("0 9 1 * *"),  # 1st of the month - matches IND's own cadence
    timeout=300,
)
def sync_sponsors() -> None:
    """Mirrors `jf sync-sponsors`, for the deployed instance's own volume."""
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
    volumes={DATA_MOUNT: volume},
    secrets=[modal.Secret.from_name("jobfinder-adzuna")],
    timeout=300,
)
def seed_jobs(query: str = "software engineer", country: str = "nl") -> None:
    """Mirrors `jf search-jobs` + `jf rescore-jobs`, for the deployed
    instance's own volume. Not scheduled - run manually (see
    deploy/README.md) to seed or top up the live site's job listings.
    """
    import os

    os.environ["JOBFINDER_DATA_DIR"] = DATA_MOUNT
    from jobfinder.jobs.adzuna import search as adzuna_search
    from jobfinder.jobs.ingest import ingest_jobs
    from jobfinder.matching.score import rescore_jobs

    listings = adzuna_search(query, country=country)
    inserted = ingest_jobs(listings)
    rescored = rescore_jobs()
    volume.commit()
    print(f"Found {len(listings)} roles, {inserted} new, {rescored} rescored")
