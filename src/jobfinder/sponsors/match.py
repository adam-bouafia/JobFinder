"""Fuzzy-match an arbitrary company name against the synced sponsor register."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process

from ..db import cursor
from .normalize import normalize

SponsorChoices = dict[str, dict[str, Any]]


@dataclass(frozen=True)
class MatchResult:
    is_sponsor: bool
    matched_name: str | None
    kvk: str | None
    score: float


def load_sponsor_choices(dsn: str | None = None) -> SponsorChoices:
    """Load the sponsor table once, for matching many names without
    re-querying/re-scanning per name (see jobs/ingest.py)."""
    with cursor(dsn) as conn:
        rows = conn.execute("SELECT kvk, name, name_normalized FROM sponsors").fetchall()
    if not rows:
        raise RuntimeError("Sponsor table is empty; run `jf sync-sponsors` first.")
    return {row["name_normalized"]: row for row in rows}


def match_against_choices(
    name: str, choices: SponsorChoices, threshold: float = 90.0
) -> MatchResult:
    """Check whether `name` matches a recognised sponsor in `choices`.

    Why token_set_ratio, not WRatio: verified live against this register
    that WRatio gives a dangerous flat ~90.0 to *any* short query against a
    long, completely unrelated candidate (it falls back to
    partial_ratio * 0.9, and a short string is trivially "contained in"
    almost anything). E.g. WRatio scored "Adien" vs "Joulz Infradiensten
    B.V." at 90.0 -- a false positive for a visa-sponsor lookup is actively
    misleading, not just noise. token_set_ratio instead compares word sets,
    so an informal/short name that is genuinely a subset of the official
    name scores 100 (e.g. "ASML" vs "ASML Netherlands B.V."), while
    unrelated short-vs-long pairs score well under 60.

    Why threshold 90: with token_set_ratio, legitimate informal-name and
    legal-suffix differences score 90-100; unrelated names stayed at or
    below 57 across every adversarial case tried (including single-word
    vs. long multi-word names). 90 keeps a wide safety margin against false
    positives, at the cost of not auto-correcting heavier typos -- an
    acceptable trade for a tool whose answer people may act on.
    """
    query = normalize(name)
    best = process.extractOne(query, choices.keys(), scorer=fuzz.token_set_ratio)
    if best is None or best[1] < threshold:
        return MatchResult(
            is_sponsor=False, matched_name=None, kvk=None, score=best[1] if best else 0.0
        )

    matched_normalized, score, _ = best
    row = choices[matched_normalized]
    return MatchResult(is_sponsor=True, matched_name=row["name"], kvk=row["kvk"], score=score)


def match_company(name: str, threshold: float = 90.0, dsn: str | None = None) -> MatchResult:
    """Check whether `name` matches a recognised sponsor.

    One-shot convenience wrapper around load_sponsor_choices +
    match_against_choices, for a single ad-hoc lookup (CLI, web UI). For
    matching many names in a batch, load the choices once instead.

    Raises:
        RuntimeError: if the sponsors table is empty (sync hasn't run yet).
    """
    choices = load_sponsor_choices(dsn)
    return match_against_choices(name, choices, threshold)
