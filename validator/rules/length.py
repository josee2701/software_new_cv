"""``length.*`` rules (spec §9.2): page count and minimum content.

``length.min_content`` estimates how full a page is from the amount of visible text when the
page count says 1 page or is unknown: a full Letter page of the ATS template holds about
``CHARS_PER_PAGE[density]`` characters (measured with WeasyPrint on the example resume:
2 pages in compact/normal, 3 in wide); below 60% of it the
document is reported as too short.
"""

from __future__ import annotations

from models.enums import Density
from validator.registry import rule
from validator.rules._common import experiences, shown, skills, visible_sections
from validator.text import html_text
from validator.types import Hit, RuleContext

MIN_FILL = 0.6
CHARS_PER_PAGE: dict[Density, int] = {
    Density.COMPACT: 2500,
    Density.NORMAL: 2100,
    Density.WIDE: 1650,
}


def page_count(ctx: RuleContext) -> int | None:
    if ctx.pages is not None:
        return ctx.pages
    return ctx.pdf.pages if ctx.pdf is not None else None


def visible_text(ctx: RuleContext) -> str:
    """Rendered text if the HTML is available; otherwise an approximation from the data."""
    if ctx.html is not None:
        return html_text(ctx.html)
    cv = ctx.cv
    keys = {s.section.value for s in visible_sections(ctx)}
    parts: list[str] = [cv.basics.full_name, cv.basics.headline, cv.basics.email]
    parts += [cv.basics.phone, cv.basics.city, *(link.url for link in cv.links)]
    if "summary" in keys:
        parts.append(cv.basics.summary or "")
    if "experience" in keys:
        for exp in experiences(ctx):
            parts += [exp.role, exp.company, exp.city or "", exp.description or ""]
            parts += [a.text for a in exp.achievements if shown(ctx, a.show_in)]
            parts += exp.technologies
    if "education" in keys:
        for edu in ctx.cv.education:
            if shown(ctx, edu.show_in):
                parts += [edu.degree, edu.institution, edu.field or "", edu.description or ""]
    if "skills" in keys:
        parts += [c.name for c in cv.skill_categories] + [s.name for s in skills(ctx)]
    if "projects" in keys:
        for proj in cv.projects:
            if shown(ctx, proj.show_in):
                parts += [proj.name, proj.role or "", proj.description, *proj.technologies]
    if "certifications" in keys:
        for cert in cv.certifications:
            if shown(ctx, cert.show_in):
                parts += [cert.name, cert.issuer, cert.credential_id or ""]
    if "languages" in keys:
        parts += [f"{lang.name} {lang.level.value}" for lang in cv.languages]
    return " ".join(" ".join(p for p in parts if p).split())


@rule(
    id="length.pages",
    section="doc",
    severity={"ats": "error", "mail": "warning"},
    weight=10,
)
def pages(ctx: RuleContext) -> list[Hit]:
    """Número de páginas ≤ ``max_pages`` del perfil (tras renderizar)."""
    count = page_count(ctx)
    if count is None or count <= ctx.profile.max_pages:
        return []
    return [
        Hit(
            f"El documento tiene {count} páginas; el perfil permite {ctx.profile.max_pages}.",
            entity="profile",
            entity_id=ctx.profile.id,
            suggestion="Recorta logros antiguos, usa densidad compacta o sube el máximo.",
        )
    ]


@rule(
    id="length.min_content",
    section="doc",
    severity={"ats": "warning", "mail": "warning"},
    weight=4,
)
def min_content(ctx: RuleContext) -> list[Hit]:
    """Contenido menor al 60% de una página: hoja de vida muy corta."""
    count = page_count(ctx)
    if count is not None and count >= 2:
        return []
    capacity = CHARS_PER_PAGE.get(ctx.profile.density, CHARS_PER_PAGE[Density.NORMAL])
    fill = len(visible_text(ctx)) / capacity
    if fill >= MIN_FILL:
        return []
    return [
        Hit(
            f"El contenido ocupa aproximadamente el {fill:.0%} de una página.",
            suggestion="Amplía logros, proyectos o habilidades para llenar al menos 60% de la "
            "página.",
        )
    ]
