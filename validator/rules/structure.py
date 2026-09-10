"""``structure.*`` rules (spec §9.2): layout of the ATS output and sections of the profile."""

from __future__ import annotations

import re

from models.enums import SectionKey
from validator.registry import rule
from validator.rules._common import experiences, section_visible, shown, visible_sections
from validator.text import fold, lang_or_default, strip_comments
from validator.types import Hit, RuleContext

# Multi-column / out-of-flow layout in the final HTML (CSS comments are ignored).
_COLUMN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("display: grid", re.compile(r"display\s*:\s*(?:inline-)?grid", re.I)),
    ("grid-template", re.compile(r"grid-template(?:-columns|-areas)?\s*:", re.I)),
    ("columns", re.compile(r"(?<![\w-])(?:columns|column-count|column-width)\s*:", re.I)),
    ("float", re.compile(r"(?<![\w-])float\s*:\s*(?:left|right)", re.I)),
    ("position: absolute", re.compile(r"position\s*:\s*(?:absolute|fixed)", re.I)),
)
_TABLE_RE = re.compile(r"<table\b", re.I)
_IMG_RE = re.compile(r"<(?:img|svg)\b", re.I)

RECOMMENDED_ORDER: tuple[SectionKey, ...] = (
    SectionKey.SUMMARY,
    SectionKey.EXPERIENCE,
    SectionKey.EDUCATION,
    SectionKey.SKILLS,
)
SECTION_LABELS: dict[SectionKey, str] = {
    SectionKey.SUMMARY: "resumen",
    SectionKey.EXPERIENCE: "experiencia",
    SectionKey.EDUCATION: "educación",
    SectionKey.SKILLS: "habilidades",
    SectionKey.PROJECTS: "proyectos",
    SectionKey.CERTIFICATIONS: "certificaciones",
    SectionKey.LANGUAGES: "idiomas",
}

# Whitelist of headings (es/en) that ATS parsers map to each section. Compared folded
# (no accents, lowercase, spaces collapsed, "&" = "y"/"and").
CANONICAL_HEADINGS: dict[SectionKey, frozenset[str]] = {
    SectionKey.SUMMARY: frozenset(
        {
            "resumen",
            "resumen profesional",
            "perfil",
            "perfil profesional",
            "extracto",
            "acerca de mi",
            "sobre mi",
            "objetivo profesional",
            "summary",
            "professional summary",
            "profile",
            "professional profile",
            "about",
            "about me",
            "career summary",
            "objective",
        }
    ),
    SectionKey.EXPERIENCE: frozenset(
        {
            "experiencia",
            "experiencia profesional",
            "experiencia laboral",
            "historial laboral",
            "trayectoria profesional",
            "trayectoria laboral",
            "experience",
            "work experience",
            "professional experience",
            "employment history",
            "work history",
            "employment",
            "career history",
        }
    ),
    SectionKey.EDUCATION: frozenset(
        {
            "educacion",
            "formacion",
            "formacion academica",
            "estudios",
            "educacion y formacion",
            "education",
            "academic background",
            "education and training",
        }
    ),
    SectionKey.SKILLS: frozenset(
        {
            "habilidades",
            "habilidades tecnicas",
            "competencias",
            "competencias tecnicas",
            "conocimientos",
            "conocimientos tecnicos",
            "aptitudes",
            "skills",
            "technical skills",
            "core competencies",
            "competencies",
            "key skills",
        }
    ),
    SectionKey.PROJECTS: frozenset(
        {
            "proyectos",
            "proyectos destacados",
            "proyectos personales",
            "projects",
            "personal projects",
            "key projects",
            "selected projects",
        }
    ),
    SectionKey.CERTIFICATIONS: frozenset(
        {
            "certificaciones",
            "certificados",
            "licencias y certificaciones",
            "cursos y certificaciones",
            "certifications",
            "certificates",
            "licenses and certifications",
            "certifications and licenses",
        }
    ),
    SectionKey.LANGUAGES: frozenset({"idiomas", "lenguas", "languages"}),
}


SUGGESTED_HEADINGS: dict[str, dict[SectionKey, str]] = {
    "es": {
        SectionKey.SUMMARY: "Resumen profesional",
        SectionKey.EXPERIENCE: "Experiencia profesional",
        SectionKey.EDUCATION: "Educación",
        SectionKey.SKILLS: "Habilidades",
        SectionKey.PROJECTS: "Proyectos",
        SectionKey.CERTIFICATIONS: "Certificaciones",
        SectionKey.LANGUAGES: "Idiomas",
    },
    "en": {
        SectionKey.SUMMARY: "Summary",
        SectionKey.EXPERIENCE: "Experience",
        SectionKey.EDUCATION: "Education",
        SectionKey.SKILLS: "Skills",
        SectionKey.PROJECTS: "Projects",
        SectionKey.CERTIFICATIONS: "Certifications",
        SectionKey.LANGUAGES: "Languages",
    },
}


def normalize_heading(title: str, lang: str) -> str:
    text = fold(title).replace("&", " y " if lang == "es" else " and ")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def is_canonical_heading(key: SectionKey, title: str) -> bool:
    accepted = CANONICAL_HEADINGS[key]
    return any(normalize_heading(title, lang) in accepted for lang in ("es", "en"))


def _html_source(ctx: RuleContext) -> str | None:
    return None if ctx.html is None else strip_comments(ctx.html)


@rule(
    id="structure.single_column",
    section="profile",
    severity={"ats": "error", "mail": "-"},
    weight=15,
)
def single_column(ctx: RuleContext) -> list[Hit]:
    """Una sola columna: el HTML final no usa grid, columnas CSS, float ni posición absoluta."""
    source = _html_source(ctx)
    if source is None:
        return []
    found = [label for label, pattern in _COLUMN_PATTERNS if pattern.search(source)]
    if not found:
        return []
    return [
        Hit(
            "La plantilla usa maquetación de varias columnas o fuera de flujo: "
            + ", ".join(found)
            + ".",
            entity="profile",
            entity_id=ctx.profile.id,
            suggestion="Usa la plantilla Plataforma de una sola columna.",
        )
    ]


@rule(
    id="structure.no_tables",
    section="profile",
    severity={"ats": "error", "mail": "-"},
    weight=15,
)
def no_tables(ctx: RuleContext) -> list[Hit]:
    """Sin ``<table>`` en el HTML final."""
    source = _html_source(ctx)
    if source is None or not _TABLE_RE.search(source):
        return []
    return [
        Hit(
            "El documento contiene tablas; muchos ATS las leen desordenadas.",
            entity="profile",
            entity_id=ctx.profile.id,
            suggestion="Usa texto y listas en lugar de tablas.",
        )
    ]


@rule(
    id="structure.no_photo",
    section="profile",
    severity={"ats": "error", "mail": "-"},
    weight=10,
)
def no_photo(ctx: RuleContext) -> list[Hit]:
    """Sin foto ni imágenes en ATS (``include_photo`` debe ser falso)."""
    hits: list[Hit] = []
    if ctx.profile.include_photo:
        hits.append(
            Hit(
                "El perfil Plataforma incluye foto.",
                entity="profile",
                entity_id=ctx.profile.id,
                suggestion="Desactiva la foto en este perfil.",
            )
        )
    source = _html_source(ctx)
    if source is not None and _IMG_RE.search(source):
        hits.append(
            Hit(
                "El documento contiene imágenes o iconos.",
                entity="profile",
                entity_id=ctx.profile.id,
                suggestion="Quita imágenes e iconos del destino Plataforma.",
            )
        )
    return hits


@rule(
    id="structure.section_order",
    section="profile",
    severity={"ats": "warning", "mail": "-"},
    weight=5,
)
def section_order(ctx: RuleContext) -> list[Hit]:
    """Orden recomendado: resumen → experiencia → educación → habilidades."""
    actual = [s.section for s in visible_sections(ctx) if s.section in RECOMMENDED_ORDER]
    expected = [key for key in RECOMMENDED_ORDER if key in actual]
    if actual == expected:
        return []
    return [
        Hit(
            "Orden de secciones: " + " → ".join(SECTION_LABELS[k] for k in actual) + ".",
            entity="profile",
            entity_id=ctx.profile.id,
            suggestion="Ordena: " + " → ".join(SECTION_LABELS[k] for k in expected) + ".",
        )
    ]


@rule(
    id="structure.canonical_headings",
    section="profile",
    severity={"ats": "error", "mail": "-"},
    weight=8,
)
def canonical_headings(ctx: RuleContext) -> list[Hit]:
    """Los títulos personalizados deben ser nombres canónicos (lista blanca es/en)."""
    hits: list[Hit] = []
    for ps in visible_sections(ctx):
        title = (ps.title_override or "").strip()
        if not title or is_canonical_heading(ps.section, title):
            continue
        hits.append(
            Hit(
                f"El título «{title}» de {SECTION_LABELS[ps.section]} no es reconocible "
                "por un ATS.",
                entity="profile_section",
                entity_id=ps.id,
                suggestion="Usa un título estándar, p. ej. «"
                + SUGGESTED_HEADINGS[lang_or_default(ctx.cv.language)][ps.section]
                + "», o quita el título personalizado.",
            )
        )
    return hits


@rule(
    id="structure.required_sections",
    section="profile",
    severity={"ats": "error", "mail": "warning"},
    weight=10,
)
def required_sections(ctx: RuleContext) -> list[Hit]:
    """Experiencia y educación visibles y con al menos un ítem."""
    counts = {
        SectionKey.EXPERIENCE: len(experiences(ctx)),
        SectionKey.EDUCATION: sum(1 for e in ctx.cv.education if shown(ctx, e.show_in)),
    }
    hits: list[Hit] = []
    for key, count in counts.items():
        label = SECTION_LABELS[key]
        if not section_visible(ctx, key):
            hits.append(
                Hit(
                    f"La sección de {label} está oculta en este perfil.",
                    entity="profile",
                    entity_id=ctx.profile.id,
                    suggestion=f"Haz visible la sección de {label}.",
                )
            )
        elif count == 0:
            hits.append(
                Hit(
                    f"La sección de {label} no tiene ítems para este destino.",
                    section=key.value,
                    suggestion=f"Agrega al menos un ítem de {label} visible en este destino.",
                )
            )
    return hits
