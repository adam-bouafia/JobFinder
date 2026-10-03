"""Extract text from a PDF's text layer - the common case for modern resumes.

Falls back to OCR (ocr.py) per-page only when a page's text layer is empty
or near-empty, which is the signal that it's a scanned image rather than
real text.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from .ocr import ocr_page

MIN_USABLE_CHARS = 20


def extract_text_layer(path: Path) -> list[str]:
    """Return each page's extracted text (empty string if none)."""
    with pdfplumber.open(path) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


def extract_text(path: Path) -> list[str]:
    """Return each page's text, using OCR for pages with no usable text layer.

    Why per-page, not per-document: a resume can mix a text-based first
    page with a scanned signature page, a screenshot, or similar.
    """
    pages = extract_text_layer(path)
    return [
        text if len(text.strip()) >= MIN_USABLE_CHARS else ocr_page(path, page_number)
        for page_number, text in enumerate(pages, start=1)
    ]
