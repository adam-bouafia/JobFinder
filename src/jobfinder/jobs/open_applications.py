"""Classify already-ingested job listings as open/speculative applications.

Deliberately not a separate crawler: open-application roles already show
up through the normal ATS ingestion (many Greenhouse boards carry an
evergreen "General Application" req, for example), this just flags the
ones that are.
"""

from __future__ import annotations

OPEN_APPLICATION_KEYWORDS: tuple[str, ...] = (
    "general application",
    "open application",
    "future opportunities",
    "talent pool",
    "talent community",
    "spontaneous sollicitatie",
    "open sollicitatie",
    "general vacancy",
    "speculative application",
    "always hiring",
)


def is_open_application(title: str) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in OPEN_APPLICATION_KEYWORDS)
