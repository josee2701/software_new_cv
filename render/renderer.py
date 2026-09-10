"""HTML rendering of a resume with a profile (spec §8)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from export.pdf import count_pages
from render.context import build_context
from schemas import ExportProfileOut, ResumeOut

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class RenderResult:
    html: str
    pages: int | None = None  # only when render(..., with_pages=True)


@lru_cache
def get_env() -> Environment:
    return Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


def render(
    cv: ResumeOut,
    profile: ExportProfileOut,
    *,
    for_preview: bool = False,
    with_pages: bool = False,
) -> RenderResult:
    """Render ``{destination}/base.html``. Raises ``jinja2.TemplateNotFound`` if missing.

    ``with_pages`` lays the document out (WeasyPrint, cached by HTML hash) to fill ``pages``;
    it is off by default because it costs a layout pass.
    """
    ctx = build_context(cv, profile, for_preview=for_preview)
    template = get_env().get_template(f"{profile.destination.value}/base.html")
    html = template.render(**ctx)
    pages = count_pages(html) if with_pages else None
    return RenderResult(html=html, pages=pages)
