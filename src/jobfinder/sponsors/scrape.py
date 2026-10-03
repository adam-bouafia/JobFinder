"""Fetch and parse the IND recognised-sponsors register (work migration)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from ..db import cursor
from .normalize import normalize

IND_URL = "https://ind.nl/en/public-register-recognised-sponsors/public-register-work"
USER_AGENT = (
    "JobFinder-SponsorSync/0.1 (personal, non-commercial; monthly sync of public IND register)"
)


@dataclass(frozen=True)
class SponsorRow:
    kvk: str
    name: str
    name_normalized: str


def fetch_html() -> str:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(IND_URL, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text


def parse(html: str) -> list[SponsorRow]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[SponsorRow] = []
    for name_cell in soup.select("tr > th[scope=row]"):
        kvk_cell = name_cell.find_next_sibling("td")
        if kvk_cell is None:
            continue
        name = " ".join(name_cell.get_text().split())
        kvk = " ".join(kvk_cell.get_text().split())
        if not name or not kvk:
            continue
        rows.append(SponsorRow(kvk=kvk, name=name, name_normalized=normalize(name)))
    return rows


def fetch_sponsors() -> list[SponsorRow]:
    """Fetch and parse the live register.

    Raises:
        RuntimeError: if parsing yields zero sponsors, since that almost
            certainly means IND changed the page markup rather than that
            the register is actually empty.
    """
    rows = parse(fetch_html())
    if not rows:
        raise RuntimeError("Parsed zero sponsors from IND register; page markup may have changed.")
    return rows


def sync_sponsors(dsn: str | None = None) -> int:
    """Fetch, parse, and upsert the IND register into the sponsors table.

    Returns the number of distinct sponsors now stored. The IND page has
    occasionally listed the same KVK number twice (confirmed against the
    live register); those collapse to one row via the upsert, so this can
    be slightly lower than the number of rows parsed off the page.
    """
    rows = fetch_sponsors()
    now = datetime.now(UTC)
    with cursor(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO sponsors (kvk, name, name_normalized, fetched_at)
                VALUES (%(kvk)s, %(name)s, %(name_normalized)s, %(fetched_at)s)
                ON CONFLICT(kvk) DO UPDATE SET
                    name=excluded.name,
                    name_normalized=excluded.name_normalized,
                    fetched_at=excluded.fetched_at
                """,
                [
                    {
                        "kvk": row.kvk,
                        "name": row.name,
                        "name_normalized": row.name_normalized,
                        "fetched_at": now,
                    }
                    for row in rows
                ],
            )
        conn.execute(
            """
            INSERT INTO meta (key, value) VALUES ('ind_synced_at', %s)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value
            """,
            (now.isoformat(timespec="seconds"),),
        )
        stored_row = conn.execute("SELECT COUNT(*) AS c FROM sponsors").fetchone()
        assert stored_row is not None  # COUNT(*) always returns exactly one row
    return int(stored_row["c"])
