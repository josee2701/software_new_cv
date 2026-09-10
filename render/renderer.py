"""HTML rendering of a resume with a profile (spec §8)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from render.context import build_context
from schemas import ExportProfileOut, ResumeOut

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class RenderResult:
    html: str
    pages: int | None = None  # filled by export/pdf.py (F2-04); None until then


@lru_cache
def get_env() -> Environment:
    return Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


def render(cv: ResumeOut, profile: ExportProfileOut, *, for_preview: bool = False) -> RenderResult:
    """Render ``{destination}/base.html``. Raises ``jinja2.TemplateNotFound`` if missing."""
    ctx = build_context(cv, profile, for_preview=for_preview)
    template = get_env().get_template(f"{profile.destination.value}/base.html")
    return RenderResult(html=template.render(**ctx), pages=None)
