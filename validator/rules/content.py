"""``content.*`` rules (spec §9.2): summary, achievements and skills."""

from __future__ import annotations

import re

from models.enums import SectionKey
from validator.registry import rule
from validator.rules._common import (
    achievements,
    all_achievements,
    excerpt,
    experiences,
    months_between,
    section_visible,
    skills,
    today,
)
from validator.text import (
    ACHIEVEMENT_PRONOUNS,
    SUMMARY_PRONOUNS,
    action_verbs,
    first_word,
    fold,
    lang_or_default,
    words,
)
from validator.types import Hit, RuleContext

SUMMARY_MIN, SUMMARY_MAX = 200, 600
ACHIEVEMENT_MIN, ACHIEVEMENT_MAX = 40, 220
MIN_ACHIEVEMENTS, MIN_ACHIEVEMENTS_SHORT, SHORT_JOB_MONTHS = 2, 1, 6
MAX_ACHIEVEMENTS = 6
METRIC_RATIO = 0.4
MIN_SKILLS = 5
_METRIC_RE = re.compile(r"\d|%|[$€£¥]|\b(?:usd|cop|eur|mxn)\b", re.I)
# Levels/bars written into a skill name ("Python 90%", "Go ★★★", "SQL (avanzado)", "8/10").
_LEVEL_RE = re.compile(
    r"%|[★☆●○■□▰▱◼◻⬤]|\b\d+\s*/\s*\d+\b|\((?:basico|intermedio|avanzado|experto|basic|"
    r"intermediate|advanced|expert|nativo|native)\)",
    re.I,
)
_PROGRESS_RE = re.compile(r"<(?:progress|meter)\b", re.I)


@rule(
    id="content.summary_length",
    section="summary",
    severity={"ats": "warning", "mail": "warning"},
    weight=4,
)
def summary_length(ctx: RuleContext) -> list[Hit]:
    """Resumen profesional de 200 a 600 caracteres."""
    if not section_visible(ctx, SectionKey.SUMMARY):
        return []
    summary = " ".join((ctx.cv.basics.summary or "").split())
    size = len(summary)
    if SUMMARY_MIN <= size <= SUMMARY_MAX:
        return []
    if size == 0:
        message = "No hay resumen profesional."
    elif size < SUMMARY_MIN:
        message = f"El resumen es muy corto ({size} caracteres)."
    else:
        message = f"El resumen es muy largo ({size} caracteres)."
    return [
        Hit(
            message,
            entity="basics",
            suggestion=f"Escribe un resumen de {SUMMARY_MIN} a {SUMMARY_MAX} caracteres.",
        )
    ]


@rule(
    id="content.summary_first_person",
    section="summary",
    severity={"ats": "warning", "mail": "info"},
    weight=2,
)
def summary_first_person(ctx: RuleContext) -> list[Hit]:
    """Evitar pronombres en primera persona («yo», «mi») en el resumen."""
    pronouns = SUMMARY_PRONOUNS[lang_or_default(ctx.cv.language)]
    found = sorted({w for w in words(ctx.cv.basics.summary or "") if w in pronouns})
    if not found:
        return []
    return [
        Hit(
            "El resumen usa primera persona: " + ", ".join(f"«{w}»" for w in found) + ".",
            entity="basics",
            suggestion="Redacta el resumen en tercera persona o de forma impersonal.",
        )
    ]


@rule(
    id="content.min_achievements",
    section="experience",
    severity={"ats": "warning", "mail": "warning"},
    weight=5,
)
def min_achievements(ctx: RuleContext) -> list[Hit]:
    """Al menos 2 logros por experiencia (1 si duró menos de 6 meses)."""
    hits: list[Hit] = []
    for exp in experiences(ctx):
        end = exp.end_date or today()
        minimum = (
            MIN_ACHIEVEMENTS_SHORT
            if months_between(exp.start_date, end) < SHORT_JOB_MONTHS
            else MIN_ACHIEVEMENTS
        )
        count = len(achievements(ctx, exp))
        if count < minimum:
            hits.append(
                Hit(
                    f"«{exp.role} — {exp.company}» tiene {count} logro(s); se recomiendan "
                    f"al menos {minimum}.",
                    entity="experience",
                    entity_id=exp.id,
                    suggestion="Agrega logros concretos con resultados medibles.",
                )
            )
    return hits


@rule(
    id="content.max_achievements",
    section="experience",
    severity={"ats": "info", "mail": "info"},
    weight=1,
)
def max_achievements(ctx: RuleContext) -> list[Hit]:
    """Máximo 6 logros por experiencia."""
    hits: list[Hit] = []
    for exp in experiences(ctx):
        count = len(achievements(ctx, exp))
        if count > MAX_ACHIEVEMENTS:
            hits.append(
                Hit(
                    f"«{exp.role} — {exp.company}» tiene {count} logros.",
                    entity="experience",
                    entity_id=exp.id,
                    suggestion=f"Deja los {MAX_ACHIEVEMENTS} más relevantes.",
                )
            )
    return hits


@rule(
    id="content.action_verb",
    section="achievement",
    severity={"ats": "warning", "mail": "warning"},
    weight=3,
)
def action_verb(ctx: RuleContext) -> list[Hit]:
    """Cada logro empieza con un verbo de acción (``validator/data/verbs_{lang}.txt``)."""
    verbs = action_verbs(ctx.cv.language)
    hits: list[Hit] = []
    for ach in all_achievements(ctx):
        word = first_word(ach.text)
        if word in verbs:
            continue
        hits.append(
            Hit(
                f"El logro «{excerpt(ach.text)}» no empieza con un verbo de acción.",
                entity="achievement",
                entity_id=ach.id,
                suggestion="Empieza con un verbo de acción: «Lideré», «Reduje», «Diseñé»…",
            )
        )
    return hits


def has_metric(text: str, metric_value: str | None) -> bool:
    return bool((metric_value or "").strip()) or bool(_METRIC_RE.search(fold(text)))


@rule(
    id="content.metric",
    section="achievement",
    severity={"ats": "warning", "mail": "info"},
    weight=3,
)
def metric(ctx: RuleContext) -> list[Hit]:
    """Al menos 40% de los logros con número, porcentaje, moneda o ``metric_value``."""
    items = all_achievements(ctx)
    if not items:
        return []
    with_metric = sum(1 for a in items if has_metric(a.text, a.metric_value))
    ratio = with_metric / len(items)
    if ratio >= METRIC_RATIO:
        return []
    return [
        Hit(
            f"Solo {with_metric} de {len(items)} logros ({ratio:.0%}) tienen una métrica.",
            section="experience",
            suggestion="Cuantifica resultados: porcentajes, tiempos, dinero, volumen.",
        )
    ]


@rule(
    id="content.achievement_length",
    section="achievement",
    severity={"ats": "warning", "mail": "warning"},
    weight=2,
)
def achievement_length(ctx: RuleContext) -> list[Hit]:
    """Logros de 40 a 220 caracteres (1–2 líneas)."""
    hits: list[Hit] = []
    for ach in all_achievements(ctx):
        size = len(" ".join(ach.text.split()))
        if ACHIEVEMENT_MIN <= size <= ACHIEVEMENT_MAX:
            continue
        kind = "corto" if size < ACHIEVEMENT_MIN else "largo"
        hits.append(
            Hit(
                f"El logro «{excerpt(ach.text)}» es muy {kind} ({size} caracteres).",
                entity="achievement",
                entity_id=ach.id,
                suggestion=f"Deja cada logro entre {ACHIEVEMENT_MIN} y {ACHIEVEMENT_MAX} "
                "caracteres.",
            )
        )
    return hits


@rule(
    id="content.no_pronouns",
    section="achievement",
    severity={"ats": "info", "mail": "-"},
    weight=1,
)
def no_pronouns(ctx: RuleContext) -> list[Hit]:
    """Evitar pronombres («yo», «nosotros») en los logros."""
    pronouns = ACHIEVEMENT_PRONOUNS[lang_or_default(ctx.cv.language)]
    hits: list[Hit] = []
    for ach in all_achievements(ctx):
        found = sorted({w for w in words(ach.text) if w in pronouns})
        if found:
            hits.append(
                Hit(
                    f"El logro «{excerpt(ach.text)}» usa pronombres: " + ", ".join(found) + ".",
                    entity="achievement",
                    entity_id=ach.id,
                    suggestion="Empieza por el verbo y omite el pronombre.",
                )
            )
    return hits


@rule(
    id="content.skills_present",
    section="skills",
    severity={"ats": "error", "mail": "warning"},
    weight=8,
)
def skills_present(ctx: RuleContext) -> list[Hit]:
    """Al menos 5 habilidades visibles."""
    count = len(skills(ctx)) if section_visible(ctx, SectionKey.SKILLS) else 0
    if count >= MIN_SKILLS:
        return []
    return [
        Hit(
            f"Hay {count} habilidad(es) visibles; se requieren al menos {MIN_SKILLS}.",
            entity="skill_category",
            suggestion="Agrega habilidades técnicas y haz visible la sección de habilidades.",
        )
    ]


@rule(
    id="content.skills_no_levels_ats",
    section="skills",
    severity={"ats": "warning", "mail": "-"},
    weight=2,
)
def skills_no_levels_ats(ctx: RuleContext) -> list[Hit]:
    """Sin barras ni porcentajes: los niveles se ocultan en ATS; no los escribas en el nombre."""
    hits = [
        Hit(
            f"La habilidad «{skill.name}» incluye un nivel o porcentaje en el nombre.",
            entity="skill",
            entity_id=skill.id,
            suggestion="Deja solo el nombre; el nivel va en su campo y no se muestra en ATS.",
        )
        for skill in skills(ctx)
        if _LEVEL_RE.search(fold(skill.name))
    ]
    if ctx.html is not None and _PROGRESS_RE.search(ctx.html):
        hits.append(
            Hit(
                "El documento muestra barras de nivel.",
                suggestion="Quita las barras de progreso del destino Plataforma.",
            )
        )
    return hits


@rule(
    id="content.keywords_from_experience",
    section="skills",
    severity={"ats": "info", "mail": "info"},
    weight=2,
)
def keywords_from_experience(ctx: RuleContext) -> list[Hit]:
    """Tecnologías usadas en experiencias que no aparecen en habilidades."""
    have = {fold(s.name) for s in skills(ctx)}
    missing: dict[str, str] = {}
    for exp in experiences(ctx):
        for tech in exp.technologies:
            key = fold(tech)
            if key not in have:
                missing.setdefault(key, tech)
    if not missing:
        return []
    names = list(missing.values())
    shown_names = ", ".join(names[:12]) + ("…" if len(names) > 12 else "")
    return [
        Hit(
            f"Tecnologías de tu experiencia que no están en habilidades: {shown_names}.",
            entity="skill_category",
            suggestion="Agrégalas a habilidades si son relevantes para la vacante.",
        )
    ]


@rule(
    id="content.duplicate_skill",
    section="skills",
    severity={"ats": "warning", "mail": "warning"},
    weight=2,
)
def duplicate_skill(ctx: RuleContext) -> list[Hit]:
    """La misma habilidad en dos categorías."""
    seen: dict[str, str] = {}
    hits: list[Hit] = []
    for cat in sorted(ctx.cv.skill_categories, key=lambda c: c.position):
        for skill in sorted(cat.skills, key=lambda s: s.position):
            key = fold(" ".join(skill.name.split()))
            if key in seen:
                hits.append(
                    Hit(
                        f"«{skill.name}» aparece en «{seen[key]}» y en «{cat.name}».",
                        entity="skill",
                        entity_id=skill.id,
                        suggestion="Deja la habilidad en una sola categoría.",
                    )
                )
            else:
                seen[key] = cat.name
    return hits
