"""ATS fetcher registry - add a new board by adding one file and one entry here."""

from __future__ import annotations

from collections.abc import Callable

from ..models import JobListing
from . import ashby, greenhouse, lever, recruitee, workable

ATS_FETCHERS: dict[str, Callable[[str], list[JobListing]]] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "recruitee": recruitee.fetch,
    "workable": workable.fetch,
}


def fetch(source: str, slug: str) -> list[JobListing]:
    """Fetch open roles from a named ATS for a company slug.

    Raises:
        KeyError: if `source` isn't a registered ATS.
    """
    return ATS_FETCHERS[source](slug)
