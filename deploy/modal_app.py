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

Search-jobs (Adzuna) isn't wired up here - the web UI doesn't expose it
(CLI-only today), so no Modal Secret is configured for those credentials.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import modal

app = modal.App("jobfinder")

# Read runtime deps from pyproject.toml itself rather than a second,
# hand-maintained list here - a hardcoded copy drifted the moment
# reportlab was added as a real dependency (PDF export needed it, but
# only pyproject.toml got updated), crash-looping the deployed container
# with ModuleNotFoundError on every request.
_PYPROJECT = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
RUNTIME_DEPENDENCIES = _PYPROJECT["project"]["dependencies"]

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
    max_containers=1,
    timeout=60,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
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
