"""HTML → PDF (spec §8.4, §10 step 4). WeasyPrint by default; Playwright/Chromium as fallback.

Never rasterizes: both engines keep real, extractable text.
"""

from __future__ import annotations

import hashlib
import importlib
import io
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from app.config import PROJECT_ROOT, get_settings

SUBJECT = "Hoja de vida"
CREATOR = "cv-ats"
_PAGE_CACHE_SIZE = 64
_page_cache: OrderedDict[str, int] = OrderedDict()


class PdfEngineError(RuntimeError):
    """The configured PDF engine is unavailable or failed."""


@dataclass(frozen=True)
class PdfResult:
    data: bytes
    pages: int


def _weasyprint_document(html: str) -> Any:
    from weasyprint import HTML

    return HTML(string=html, base_url=str(PROJECT_ROOT)).render()


def _weasyprint(html: str, title: str, author: str) -> PdfResult:
    document = _weasyprint_document(html)
    metadata = document.metadata
    metadata.title = title
    metadata.authors = [author] if author else []
    metadata.description = SUBJECT  # → /Subject
    metadata.generator = CREATOR  # → /Creator
    data: bytes = document.write_pdf()
    return PdfResult(data=data, pages=len(document.pages))


def _playwright(html: str) -> PdfResult:
    """Chromium fallback. Title comes from ``<title>``; /Author cannot be set by Chromium."""
    try:
        sync_api = importlib.import_module("playwright.sync_api")
    except ModuleNotFoundError as exc:
        raise PdfEngineError(
            "PDF_ENGINE=playwright pero Playwright no está instalado. Instálalo con "
            "`uv sync --group pdf-fallback` y `uv run playwright install chromium`."
        ) from exc
    import pdfplumber

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            data: bytes = page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = len(pdf.pages)
    return PdfResult(data=data, pages=pages)


def html_to_pdf(
    html: str, *, title: str = "", author: str = "", engine: str | None = None
) -> PdfResult:
    """Render ``html`` to PDF bytes with metadata title/author/subject/creator."""
    engine = engine or get_settings().PDF_ENGINE
    if engine == "playwright":
        result = _playwright(html)
    elif engine == "weasyprint":
        result = _weasyprint(html, title, author)
    else:
        raise PdfEngineError(f"Motor de PDF desconocido: {engine}")
    _remember_pages(html, result.pages)
    return result


def _key(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _remember_pages(html: str, pages: int) -> None:
    key = _key(html)
    _page_cache[key] = pages
    _page_cache.move_to_end(key)
    while len(_page_cache) > _PAGE_CACHE_SIZE:
        _page_cache.popitem(last=False)


def count_pages(html: str) -> int:
    """Page count of ``html`` (layout only, no PDF bytes). Cached by content hash."""
    key = _key(html)
    if key in _page_cache:
        _page_cache.move_to_end(key)
        return _page_cache[key]
    pages = len(_weasyprint_document(html).pages)
    _remember_pages(html, pages)
    return pages
