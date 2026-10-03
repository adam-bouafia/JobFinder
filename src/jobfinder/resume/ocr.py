"""OCR fallback for PDF pages with no extractable text layer (scanned resumes).

Needs the `tesseract` binary on PATH (not a pip package - install via the
system package manager, e.g. `sudo dnf install tesseract` on Fedora).
Raises pytesseract.TesseractNotFoundError if it's missing; the text-layer
path in extract.py works fine without it for ordinary, non-scanned PDFs.
"""

from __future__ import annotations

from pathlib import Path

import pytesseract
from pdf2image import convert_from_path


def ocr_page(path: Path, page_number: int) -> str:
    """Render one page (1-indexed) to an image and OCR it."""
    images = convert_from_path(path, first_page=page_number, last_page=page_number)
    if not images:
        return ""
    return str(pytesseract.image_to_string(images[0]))
