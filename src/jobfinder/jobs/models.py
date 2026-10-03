"""Shared job-listing shape across all ingestion sources."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobListing:
    company_name: str
    title: str
    location: str | None
    url: str
    source: str
    description: str | None = None
