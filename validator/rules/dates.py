"""``dates.*`` rules (spec §9.2)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from validator.registry import rule
from validator.rules._common import excerpt, experiences, month_start, months_between, shown, today
from validator.text import fold, html_text
from validator.types import Hit, RuleContext

DATE_FORMATS = ("MM/YYYY", "MMM YYYY", "YYYY")
GAP_MONTHS = 6
_MONTHS = (
    "ene|feb|mar|abr|may|jun|jul|ago|sep|sept|oct|nov|dic|"
    "jan|apr|aug|dec|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
    "noviembre|diciembre|january|february|march|april|june|july|august|september|october|"
    "november|december"
)
# Written dates by format (bare years are ambiguous and are not checked).
DATE_PATTERNS: dict[str, re.Pattern[str]] = {
    "MM/YYYY": re.compile(r"(?<![\d/])(?:0?[1-9]|1[0-2])\s*[/\-.]\s*(?:19|20)\d{2}(?![\d/])"),
    "MMM YYYY": re.compile(rf"\b(?:{_MONTHS})\.?(?:\s+de)?\s+(?:19|20)\d{{2}}\b"),
}


@dataclass(frozen=True)
class _Text:
    text: str
    entity: str | None
    entity_id: int | None


def _free_texts(ctx: RuleContext) -> Iterator[_Text]:
    """User-written text fields that may contain hand-typed dates."""
    basics = ctx.cv.basics
    yield _Text(basics.summary or "", "basics", None)
    yield _Text(basics.headline or "", "basics", None)
    for exp in experiences(ctx):
        yield _Text(exp.description or "", "experience", exp.id)
        for ach in exp.achievements:
            if shown(ctx, ach.show_in):
                yield _Text(ach.text, "achievement", ach.id)
    for edu in ctx.cv.education:
        if shown(ctx, edu.show_in):
            yield _Text(f"{edu.degree} {edu.description or ''}", "education", edu.id)
    for proj in ctx.cv.projects:
        if shown(ctx, proj.show_in):
            yield _Text(f"{proj.name} {proj.description}", "project", proj.id)
    for cert in ctx.cv.certifications:
        if shown(ctx, cert.show_in):
            yield _Text(cert.name, "certification", cert.id)


def _other_formats(text: str, expected: str) -> list[str]:
    folded = fold(text)
    return [
        match.group(0)
        for fmt, pattern in DATE_PATTERNS.items()
        if fmt != expected
        for match in pattern.finditer(folded)
    ]


@rule(
    id="dates.format_consistent",
    section="all",
    severity={"ats": "error", "mail": "warning"},
    weight=6,
)
def format_consistent(ctx: RuleContext) -> list[Hit]:
    """Un solo formato de fecha: el del perfil. Detecta fechas escritas a mano en otro formato."""
    expected = ctx.profile.date_format
    if expected not in DATE_FORMATS:
        return [
            Hit(
                f"Formato de fecha desconocido en el perfil: «{expected}».",
                section="profile",
                entity="profile",
                entity_id=ctx.profile.id,
                suggestion="Elige MM/YYYY, MMM YYYY o YYYY.",
            )
        ]
    hits: list[Hit] = []
    for item in _free_texts(ctx):
        found = _other_formats(item.text, expected)
        if found:
            hits.append(
                Hit(
                    f"«{excerpt(item.text)}» contiene fechas en otro formato ({found[0]}); "
                    f"el perfil usa {expected}.",
                    entity=item.entity,
                    entity_id=item.entity_id,
                    suggestion=f"Escribe las fechas como {expected} o quítalas del texto.",
                )
            )
    if not hits and ctx.html is not None:
        found = _other_formats(html_text(ctx.html), expected)
        if found:
            hits.append(
                Hit(
                    f"El documento mezcla formatos de fecha ({found[0]}); "
                    f"el perfil usa {expected}.",
                    suggestion=f"Usa solo el formato {expected}.",
                )
            )
    return hits


@rule(
    id="dates.chronological",
    section="experience",
    severity={"ats": "warning", "mail": "info"},
    weight=3,
)
def chronological(ctx: RuleContext) -> list[Hit]:
    """Experiencias en orden cronológico inverso (la más reciente primero)."""
    items = experiences(ctx)
    for previous, current in pairwise(items):
        prev_key = (previous.is_current, previous.end_date or date.max, previous.start_date)
        curr_key = (current.is_current, current.end_date or date.max, current.start_date)
        if current.start_date > previous.start_date or curr_key > prev_key:
            return [
                Hit(
                    f"«{current.role} — {current.company}» es más reciente que la experiencia "
                    "anterior en la lista.",
                    entity="experience",
                    entity_id=current.id,
                    suggestion="Ordena las experiencias de la más reciente a la más antigua.",
                )
            ]
    return []


@rule(
    id="dates.gap",
    section="experience",
    severity={"ats": "info", "mail": "-"},
    weight=1,
)
def gap(ctx: RuleContext) -> list[Hit]:
    """Huecos de más de 6 meses entre experiencias (solo informa)."""
    items = sorted(experiences(ctx), key=lambda e: e.start_date)
    hits: list[Hit] = []
    covered_until: date | None = None
    for exp in items:
        if covered_until is not None:
            months = months_between(covered_until, exp.start_date)
            if months > GAP_MONTHS:
                hits.append(
                    Hit(
                        f"Hay un periodo de {months} meses sin experiencia antes de "
                        f"«{exp.role} — {exp.company}».",
                        entity="experience",
                        entity_id=exp.id,
                        suggestion="Si aplica, explica el periodo (estudios, proyecto propio…).",
                    )
                )
        end = exp.end_date or month_start(today())
        covered_until = end if covered_until is None else max(covered_until, end)
    return hits


@rule(
    id="dates.overlap_current",
    section="experience",
    severity={"ats": "warning", "mail": "warning"},
    weight=2,
)
def overlap_current(ctx: RuleContext) -> list[Hit]:
    """Más de una experiencia marcada como actual."""
    current = [e for e in experiences(ctx) if e.is_current or e.end_date is None]
    if len(current) <= 1:
        return []
    return [
        Hit(
            f"{len(current)} experiencias están marcadas como actuales.",
            entity="experience",
            entity_id=current[1].id,
            suggestion="Deja como actual solo tu trabajo vigente.",
        )
    ]


def _dated(ctx: RuleContext) -> Iterator[tuple[str, int, str, date | None, date | None]]:
    """``(entity, id, label, start, end)`` of every dated item shown for the destination."""
    for exp in experiences(ctx):
        yield "experience", exp.id, f"{exp.role} — {exp.company}", exp.start_date, exp.end_date
    for edu in ctx.cv.education:
        if shown(ctx, edu.show_in):
            end = None if edu.in_progress else edu.end_date  # expected graduation may be future
            yield "education", edu.id, edu.degree, edu.start_date, end
    for proj in ctx.cv.projects:
        if shown(ctx, proj.show_in):
            yield "project", proj.id, proj.name, proj.start_date, proj.end_date
    for cert in ctx.cv.certifications:
        if shown(ctx, cert.show_in):
            yield "certification", cert.id, cert.name, cert.issue_date, None  # expiry exempt


@rule(
    id="dates.future",
    section="all",
    severity={"ats": "error", "mail": "error"},
    weight=5,
)
def future(ctx: RuleContext) -> list[Hit]:
    """Fechas futuras (excepto vencimiento de certificaciones y grado esperado en curso)."""
    limit = month_start(today())
    hits: list[Hit] = []
    for entity, entity_id, label, start, end in _dated(ctx):
        if any(d is not None and month_start(d) > limit for d in (start, end)):
            hits.append(
                Hit(
                    f"«{label}» tiene una fecha futura.",
                    entity=entity,
                    entity_id=entity_id,
                    suggestion="Corrige la fecha; usa «actual» o «en curso» para lo vigente.",
                )
            )
    return hits


@rule(
    id="dates.end_before_start",
    section="all",
    severity={"ats": "error", "mail": "error"},
    weight=5,
)
def end_before_start(ctx: RuleContext) -> list[Hit]:
    """Fecha de fin anterior a la de inicio (incluye vencimiento antes de expedición)."""
    pairs = [(e, i, lbl, s, f) for e, i, lbl, s, f in _dated(ctx) if e != "certification"]
    pairs += [
        ("certification", c.id, c.name, c.issue_date, c.expiry_date)
        for c in ctx.cv.certifications
        if shown(ctx, c.show_in)
    ]
    pairs += [
        ("education", e.id, e.degree, e.start_date, e.end_date)
        for e in ctx.cv.education
        if shown(ctx, e.show_in) and e.in_progress
    ]
    return [
        Hit(
            f"«{label}» termina antes de empezar.",
            entity=entity,
            entity_id=entity_id,
            suggestion="Revisa las fechas de inicio y fin.",
        )
        for entity, entity_id, label, start, end in pairs
        if start is not None and end is not None and end < start
    ]
