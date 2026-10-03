"""Normalize company names for fuzzy matching against the sponsor register."""

from __future__ import annotations

import re
import unicodedata

_LEGAL_SUFFIXES = re.compile(
    r"\b(b\.?v\.?|n\.?v\.?|holding|group|international|nederland|netherlands|"
    r"europe|services|llc|llp|inc\.?|ltd\.?|gmbh)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Reduce a company name to a casing/punctuation/suffix-insensitive form.

    Why: job-board and IND register spellings of the same company rarely
    match exactly (e.g. "Booking.com" vs "Booking.com B.V.", or stray
    leading symbols like "@EasePay B.V." seen in the real register data),
    so matching needs a normalized form rather than the raw string.
    """
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().lstrip("@#* ")
    text = _LEGAL_SUFFIXES.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text
