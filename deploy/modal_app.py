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
Recruitee/Workable), plus JSearch via `jf search-jobs` (CLI-only, see
jobs/jsearch.py) - every link shown is the employer's own posting, never
an aggregator redirect. Adzuna was tried and dropped (see
docs/architecture.md's risk table): its API terms require a visible
"Jobs by Adzuna" attribution badge, which conflicts with a clean,
direct-to-employer open-source product. Run `seed_jobs` once manually
after a fresh database (see deploy/README.md) to pull a company's board;
it isn't scheduled, since which companies to track is a deliberate,
manual choice, not something to auto-refresh.

Search is Meilisearch, self-hosted here too (`meilisearch_server`, via
`@modal.web_server` - built specifically for running an arbitrary non-
Python HTTP server binary inside a container, see
modal.com/docs/reference/modal.web_server). A plain debian_slim image
with the binary installed via Meilisearch's own install script, not
`Image.from_registry` on the official Docker image: Modal's docs warn
that a custom base image's ENTRYPOINT has to `exec "$@"` for Modal's own
Python runtime to take over afterward, and the official Meilisearch
image's entrypoint is built to launch meilisearch directly as PID 1, not
hand off control - safer to keep Modal's own proven debian_slim +
Python entrypoint and just drop the binary into it.

Deliberately NOT backed by a Modal Volume: hit a real, known Meilisearch
bug live ("failed to infer the version of the database", its VERSION
file not surviving a write on certain cloud/container filesystems -
github.com/meilisearch/meilisearch/issues/4584) - the same category of
problem (non-standard write durability) that motivated dropping SQLite-
on-a-Volume in the first place. Runs on the container's own local disk
instead, which means the index is lost on every container restart/
redeploy - an accepted tradeoff since Postgres is the system of record
and the index is designed to be derived/rebuildable (see
search/meilisearch_client.py): `rescore_jobs()` already reindexes every
row as a side effect, so the next resume upload (or a manual `jf
rescore-jobs` / the `seed_jobs` function) naturally heals it. If
Meilisearch is ever down entirely, the CLI and /export still work fully
against Postgres directly, and the web UI falls back to a plain
(non-ranked) Postgres query automatically.
"""

from __future__ import annotations

from collections.abc import MutableMapping

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

meili_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "ca-certificates")
    .run_commands(
        "curl -L https://install.meilisearch.com | sh",
        "mv ./meilisearch /usr/local/bin/meilisearch",
    )
)
DB_SECRET = modal.Secret.from_name("jobfinder-db")
SEARCH_SECRET = modal.Secret.from_name("jobfinder-search")
RAPIDAPI_SECRET = modal.Secret.from_name("jobfinder-rapidapi")

# Modal assigns this URL from the label below - hardcoded here too so the
# other functions can point MEILISEARCH_URL at it without needing a
# second secret just to duplicate a value Modal already determines.
MEILISEARCH_LABEL = "jobfinder-search"
MEILISEARCH_URL = f"https://adam-bouafia--{MEILISEARCH_LABEL}.modal.run"


def _point_at_search(env: MutableMapping[str, str]) -> None:
    """Shared by every function that calls meilisearch_client: reuses the
    one jobfinder-search Secret's MEILI_MASTER_KEY (what the Meilisearch
    binary itself expects) as MEILISEARCH_KEY (what meilisearch_client.py
    expects) - same credential, two env var names, no second secret."""
    env["MEILISEARCH_URL"] = MEILISEARCH_URL
    env["MEILISEARCH_KEY"] = env["MEILI_MASTER_KEY"]


@app.function(
    image=meili_image,
    secrets=[SEARCH_SECRET],
    max_containers=1,
    timeout=600,
)
@modal.concurrent(max_inputs=50)
@modal.web_server(7700, startup_timeout=30, label=MEILISEARCH_LABEL)
def meilisearch_server():  # type: ignore[no-untyped-def]  # Modal's own decorator, not typed for strict mypy
    import os
    import subprocess

    env = os.environ.copy()
    env["MEILI_NO_ANALYTICS"] = "true"
    # Explicit, not relying on the default: confirmed live that newer
    # Meilisearch versions (the install script grabs latest - v1.54.3 vs
    # the v1.11 Docker image tested locally) default to binding
    # 127.0.0.1, not 0.0.0.0, which Modal's web_server can't reach.
    env["MEILI_HTTP_ADDR"] = "0.0.0.0:7700"
    # No MEILI_DB_PATH override - local container disk, not a Volume. See
    # module docstring for why: a Modal Volume hit Meilisearch's own
    # "failed to infer the version of the database" bug (its VERSION file
    # not surviving a write on that filesystem), so the index is
    # deliberately ephemeral here rather than fighting that.
    subprocess.Popen(["meilisearch"], env=env)


@app.function(
    image=image,
    volumes={DATA_MOUNT: volume},
    secrets=[DB_SECRET, SEARCH_SECRET],
    max_containers=1,
    timeout=60,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app(label="jobfinder")  # https://<workspace>--jobfinder.modal.run, not -web
def web():  # type: ignore[no-untyped-def]  # Modal's own decorator, not typed for strict mypy
    import os

    os.environ["JOBFINDER_DATA_DIR"] = DATA_MOUNT
    _point_at_search(os.environ)
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
    secrets=[DB_SECRET, SEARCH_SECRET],
    timeout=300,
)
def seed_jobs(source: str = "greenhouse", slug: str = "stripe") -> None:
    """Mirrors `jf fetch-jobs` + `jf rescore-jobs`, for the deployed
    instance's Postgres (and search index). Not scheduled - run manually
    (see deploy/README.md) to add or top up a company's roles on the live
    site. No Volume needed here: this only ever writes to Postgres/search.
    """
    import os

    _point_at_search(os.environ)
    from jobfinder.jobs.ats import fetch as ats_fetch
    from jobfinder.jobs.ingest import ingest_jobs
    from jobfinder.matching.score import rescore_jobs

    listings = ats_fetch(source, slug)
    inserted = ingest_jobs(listings)
    rescored = rescore_jobs()
    print(f"Found {len(listings)} roles, {inserted} new, {rescored} rescored")


@app.function(
    image=image,
    secrets=[DB_SECRET, SEARCH_SECRET, RAPIDAPI_SECRET],
    timeout=300,
)
def search_jobs(query: str, country: str = "nl") -> None:
    """Mirrors `jf search-jobs` + `jf rescore-jobs`, for the deployed
    instance's Postgres (and search index) - the broad-coverage
    counterpart to seed_jobs (which only pulls one company's own board at
    a time). Not scheduled, same reasoning as seed_jobs: which queries to
    run is a deliberate, manual choice (and JSearch's free tier is
    200 requests/month, one request per call here)."""
    import os

    _point_at_search(os.environ)
    from jobfinder.jobs.ingest import ingest_jobs
    from jobfinder.jobs.jsearch import search as jsearch_search
    from jobfinder.matching.score import rescore_jobs

    listings = jsearch_search(query, country=country)
    inserted = ingest_jobs(listings)
    rescored = rescore_jobs()
    print(f"Found {len(listings)} direct-link roles, {inserted} new, {rescored} rescored")
