"""Round-trip verification of a generated PDF (spec §9.3) → ``validator.types.PdfInfo``."""

from __future__ import annotations

import io
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

import pdfplumber
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1

from models.enums import ShowIn
from schemas import ExportProfileOut, ResumeOut
from validator.types import PdfInfo

ALLOWED_SYMBOLS = frozenset("•–—·")
_NON_WORD = re.compile(r"[^0-9a-z]+")
_EMBEDDED_KEYS = ("FontFile", "FontFile2", "FontFile3")


def normalize(text: str) -> str:
    """Lowercase, without accents or punctuation (spaces collapsed)."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(_NON_WORD.sub(" ", plain.lower()).split())


def tokenize(text: str) -> set[str]:
    """Normalized tokens of 2+ characters."""
    return {tok for tok in normalize(text).split() if len(tok) >= 2}


def _visible(show_in: ShowIn, profile: ExportProfileOut | None) -> bool:
    return profile is None or show_in.value in (ShowIn.BOTH.value, profile.destination.value)


def cv_texts(cv: ResumeOut, profile: ExportProfileOut | None = None) -> list[str]:
    """Texts checked by the round-trip: name, companies, roles, achievements, skills.

    With ``profile``, only content shown in that destination (show_in + visible sections).
    """
    sections = {s.section.value for s in profile.sections if s.visible} if profile else None

    def shown(key: str) -> bool:
        return sections is None or key in sections

    texts = [cv.basics.full_name]
    if shown("experience"):
        for exp in cv.experiences:
            if not _visible(exp.show_in, profile):
                continue
            texts += [exp.company, exp.role]
            texts += [a.text for a in exp.achievements if _visible(a.show_in, profile)]
    if shown("skills"):
        for cat in cv.skill_categories:
            texts += [s.name for s in cat.skills if _visible(s.show_in, profile)]
    return texts


def cv_tokens(cv: ResumeOut, profile: ExportProfileOut | None = None) -> set[str]:
    tokens: set[str] = set()
    for text in cv_texts(cv, profile):
        tokens |= tokenize(text)
    return tokens


def _font_descriptor(font: dict[str, Any]) -> dict[str, Any] | None:
    descriptor = font.get("FontDescriptor")
    if descriptor is None and font.get("DescendantFonts"):
        descendant = resolve1(resolve1(font["DescendantFonts"])[0])
        descriptor = descendant.get("FontDescriptor")
    resolved = resolve1(descriptor) if descriptor is not None else None
    return resolved if isinstance(resolved, dict) else None


def _fonts(data: bytes) -> tuple[tuple[str, ...], bool]:
    """Font base names used by the document and whether all of them are embedded."""
    names: set[str] = set()
    embedded = True
    document = PDFDocument(PDFParser(io.BytesIO(data)))
    for page in PDFPage.create_pages(document):
        fonts = resolve1((page.resources or {}).get("Font", {})) or {}
        for ref in fonts.values():
            font = resolve1(ref)
            if not isinstance(font, dict):
                continue
            base = font.get("BaseFont")
            names.add(str(getattr(base, "name", base or "?")))
            if str(getattr(font.get("Subtype"), "name", "")) == "Type3":
                continue  # glyphs are defined inside the PDF
            descriptor = _font_descriptor(font)
            if descriptor is None or not any(k in descriptor for k in _EMBEDDED_KEYS):
                embedded = False
    return tuple(sorted(names)), embedded


def _meta_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def non_latin1(chars: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted({c for c in chars if ord(c) > 0xFF and c not in ALLOWED_SYMBOLS and c.strip()})
    )


def verify(
    pdf_bytes: bytes,
    cv: ResumeOut,
    *,
    filename: str | None = None,
    profile: ExportProfileOut | None = None,
) -> PdfInfo:
    """Extract the PDF text and compare it with the resume (spec §9.3)."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = len(pdf.pages)
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        metadata = pdf.metadata or {}
    fonts, fonts_embedded = _fonts(pdf_bytes)

    expected = cv_tokens(cv, profile)
    found = tokenize(text)
    coverage = len(expected & found) / len(expected) if expected else 1.0
    compact = re.sub(r"\s+", "", text).lower()
    email = cv.basics.email.strip().lower()
    phone_digits = re.sub(r"\D", "", cv.basics.phone)
    return PdfInfo(
        pages=pages,
        coverage=round(coverage, 4),
        has_text=bool(text.strip()),
        email_found=bool(email) and email in compact,
        phone_found=bool(phone_digits) and phone_digits in re.sub(r"\D", "", text),
        fonts=fonts,
        fonts_embedded=fonts_embedded,
        non_latin1_chars=non_latin1(text),
        missing_tokens=tuple(sorted(expected - found)[:20]),
        title=_meta_str(metadata.get("Title")),
        author=_meta_str(metadata.get("Author")),
        filename=filename,
    )
