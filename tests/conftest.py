"""Shared test fixtures: a real, throwaway Postgres for every test that
needs one (SQLite is gone - see docs/architecture.md).

One podman container for the whole test session (fast - no per-test
container startup cost); each test gets its own freshly created schema
within it, via a DSN with `options=-c search_path=...` embedded, so tests
stay fully isolated from each other without needing a fresh container per
test. Matches this project's stated preference for testing against real
behavior rather than mocks (see CLAUDE.md dev_workflow.md).

Needs `podman` (or anything that understands `podman run`/`podman port`/
`podman rm`) on PATH; confirmed available without sudo in this repo's dev
environment.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from collections.abc import Iterator
from urllib.parse import quote

import httpx
import psycopg
import pytest

_IMAGE = "docker.io/library/postgres:16-alpine"
_CONTAINER_NAME = "jobfinder-pytest-pg"
_MEILI_IMAGE = "docker.io/getmeili/meilisearch:v1.11"
_MEILI_CONTAINER_NAME = "jobfinder-pytest-meili"
_MEILI_KEY = "pytest-master-key-at-least-16-bytes"


@pytest.fixture(scope="session")
def postgres_base_dsn() -> Iterator[str]:
    subprocess.run(["podman", "rm", "-f", _CONTAINER_NAME], capture_output=True, check=False)
    subprocess.run(
        [
            "podman",
            "run",
            "--rm",
            "-d",
            "--name",
            _CONTAINER_NAME,
            "-p",
            "5432",
            "-e",
            "POSTGRES_PASSWORD=jobfinder",
            "-e",
            "POSTGRES_DB=jobfinder",
            _IMAGE,
        ],
        check=True,
        capture_output=True,
    )
    port_output = subprocess.run(
        ["podman", "port", _CONTAINER_NAME, "5432/tcp"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    # e.g. "0.0.0.0:34567" - take the port after the last colon.
    host_port = port_output.rsplit(":", 1)[-1]
    dsn = f"postgresql://postgres:jobfinder@localhost:{host_port}/jobfinder"

    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=2):
                break
        except psycopg.OperationalError as error:
            last_error = error
            time.sleep(0.5)
    else:
        raise RuntimeError(f"Postgres test container never became ready: {last_error}")

    yield dsn

    subprocess.run(["podman", "rm", "-f", _CONTAINER_NAME], capture_output=True, check=False)


@pytest.fixture
def dsn(postgres_base_dsn: str) -> Iterator[str]:
    """A DSN scoped to a fresh, empty schema - full isolation between
    tests without a new container per test."""
    schema = f"test_{uuid.uuid4().hex}"
    with psycopg.connect(postgres_base_dsn) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")

    scoped_dsn = f"{postgres_base_dsn}?options={quote(f'-c search_path={schema}')}"
    yield scoped_dsn

    with psycopg.connect(postgres_base_dsn) as conn:
        conn.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture(scope="session")
def _meilisearch_container() -> Iterator[tuple[str, str]]:
    """One podman Meilisearch container for the whole test session - just
    the (url, key), no env var side effects here (see `meilisearch_env`
    below for why: a session fixture's `os.environ` writes would leak
    into every test that runs afterward, not just the ones that asked for
    Meilisearch - confirmed live, it broke unrelated web/test_app.py
    tests by making their ingest_jobs() calls silently write into a
    shared, unisolated default "jobs" index).

    127.0.0.1, not localhost: this machine resolves localhost to ::1
    first and podman's rootless port-forward (pasta) only binds IPv4 -
    confirmed live, a real connection hang otherwise.
    """
    subprocess.run(["podman", "rm", "-f", _MEILI_CONTAINER_NAME], capture_output=True, check=False)
    subprocess.run(
        [
            "podman",
            "run",
            "--rm",
            "-d",
            "--name",
            _MEILI_CONTAINER_NAME,
            "-p",
            "7700",
            "-e",
            f"MEILI_MASTER_KEY={_MEILI_KEY}",
            "-e",
            "MEILI_NO_ANALYTICS=true",
            _MEILI_IMAGE,
        ],
        check=True,
        capture_output=True,
    )
    port_output = subprocess.run(
        ["podman", "port", _MEILI_CONTAINER_NAME, "7700/tcp"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    host_port = port_output.rsplit(":", 1)[-1]
    url = f"http://127.0.0.1:{host_port}"

    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                break
        except httpx.HTTPError as error:
            last_error = error
        time.sleep(0.5)
    else:
        raise RuntimeError(f"Meilisearch test container never became ready: {last_error}")

    yield url, _MEILI_KEY

    subprocess.run(["podman", "rm", "-f", _MEILI_CONTAINER_NAME], capture_output=True, check=False)


@pytest.fixture
def meilisearch_env(
    _meilisearch_container: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str]:
    """Points MEILISEARCH_URL/MEILISEARCH_KEY at the shared test container
    for exactly the duration of one test - `monkeypatch` (function-scoped)
    reverts this automatically afterward, unlike setting os.environ
    directly in a session fixture."""
    url, key = _meilisearch_container
    monkeypatch.setenv("MEILISEARCH_URL", url)
    monkeypatch.setenv("MEILISEARCH_KEY", key)
    return url, key


@pytest.fixture
def search_index(meilisearch_env: tuple[str, str]) -> Iterator[str]:
    """A fresh, uniquely-named Meilisearch index per test - full isolation
    without a new container per test, same idea as the Postgres `dsn`
    fixture's schema-per-test."""
    from jobfinder.search import meilisearch_client

    index = f"test_{uuid.uuid4().hex}"
    yield index
    meilisearch_client.delete_index(index)
