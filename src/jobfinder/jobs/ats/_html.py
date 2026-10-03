"""Shared HTML-to-plain-text helper for ATS job descriptions."""

from __future__ import annotations

from bs4 import BeautifulSoup

# Only these introduce a line break - inline tags (b, a, span, ...) stay
# merged into the surrounding sentence. get_text()'s own `separator` arg
# can't make that distinction: it applies between every text node, block
# or inline alike.
_BLOCK_TAGS = ("p", "li", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr")


def plain_text(html: object) -> str | None:
    """Strip HTML tags from an ATS description field, or None if absent."""
    if not isinstance(html, str) or not html.strip():
        return None
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n")
    lines = [line.strip() for line in soup.get_text().splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned or None
