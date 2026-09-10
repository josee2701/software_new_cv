"""PDF generation (spec §8.4, §10, §14: pages, metadata, templates, themes, density)."""

from __future__ import annotations

import importlib.util
import io

import pdfplumber
import pytest
from sqlalchemy.orm import Session

import export.pdf as pdf_module
from export.pdf import PdfEngineError, count_pages, html_to_pdf
from models.enums import Density, Destination
from render.renderer import render
from tests._export_helpers import profile_of, seeded_cv


def _text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_ats_pdf_pages_text_and_metadata(session: Session) -> None:
    cv = seeded_cv(session)
    html = render(cv, profile_of(cv, Destination.ATS)).html
    result = html_to_pdf(html, title="Andrés — Hoja de vida", author="Andrés Felipe")
    assert result.data.startswith(b"%PDF")
    assert 1 <= result.pages <= 2
    with pdfplumber.open(io.BytesIO(result.data)) as pdf:
        assert len(pdf.pages) == result.pages
        meta = pdf.metadata
    assert meta["Title"] == "Andrés — Hoja de vida"
    assert meta["Author"] == "Andrés Felipe"
    assert meta["Subject"] == "Hoja de vida"
    assert meta["Creator"] == "cv-ats"
    text = _text(result.data)
    assert "Andrés Felipe Rojas Martínez" in text
    assert "EXPERIENCIA PROFESIONAL" in text


@pytest.mark.parametrize("theme", ["slate", "ocean", "graphite"])
def test_mail_pdf_each_theme(session: Session, theme: str) -> None:
    cv = seeded_cv(session)
    profile = profile_of(cv, Destination.MAIL).model_copy(update={"theme": theme})
    html = render(cv, profile).html
    assert f"theme-{theme}" in html
    result = html_to_pdf(html, title="t", author="a")
    assert result.pages >= 1
    assert "Banco Andino Digital" in _text(result.data)


def test_mail_accent_color_changes_output(session: Session) -> None:
    cv = seeded_cv(session)
    profile = profile_of(cv, Destination.MAIL)
    plain = render(cv, profile).html
    accent = render(cv, profile.model_copy(update={"accent_color": "#B4432F"})).html
    assert "#B4432F" in accent and "#B4432F" not in plain


def test_density_changes_pages(session: Session) -> None:
    cv = seeded_cv(session)
    ats = profile_of(cv, Destination.ATS)
    pages = {
        d: count_pages(render(cv, ats.model_copy(update={"density": d})).html) for d in Density
    }
    assert pages[Density.COMPACT] <= pages[Density.NORMAL] <= pages[Density.WIDE]
    assert pages[Density.COMPACT] < pages[Density.WIDE]


def test_render_with_pages_and_count_cache(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    cv = seeded_cv(session)
    profile = profile_of(cv, Destination.ATS)
    assert render(cv, profile).pages is None  # no layout unless asked
    first = render(cv, profile, with_pages=True)
    assert first.pages is not None and first.pages >= 1

    calls: list[str] = []
    original = pdf_module._weasyprint_document

    def spy(html: str) -> object:
        calls.append(html)
        return original(html)

    monkeypatch.setattr(pdf_module, "_weasyprint_document", spy)
    assert render(cv, profile, with_pages=True).pages == first.pages
    assert calls == []  # served from the cache (same HTML)


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is not None, reason="Playwright está instalado"
)
def test_playwright_engine_missing_gives_clear_error() -> None:
    with pytest.raises(PdfEngineError, match="Playwright no está instalado"):
        html_to_pdf("<p>x</p>", engine="playwright")


def test_unknown_engine() -> None:
    with pytest.raises(PdfEngineError, match="desconocido"):
        html_to_pdf("<p>x</p>", engine="nope")
