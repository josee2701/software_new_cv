"""Build the Jinja context EXACTLY as documented in ``docs/RENDER_CONTEXT.md``.

Input: ``ResumeOut`` + ``ExportProfileOut`` (never the ORM). UI labels come from
``web/i18n/{es,en}.json`` (owned by Design); only what is missing there lives here.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from models.enums import Destination, SectionKey, ShowIn
from render.filters import fmt_date, fmt_range, initials, phone_display, url_display, years_label
from schemas import AssetOut, ExportProfileOut, ResumeOut

I18N_DIR = PROJECT_ROOT / "web" / "i18n"

# Not present in web/i18n/*.json (reported to the lead).
DOC_TITLE_SUFFIX = {"es": "Hoja de vida", "en": "Resume"}
LINK_LABELS: dict[str, dict[str, str]] = {
    "es": {
        "linkedin": "LinkedIn",
        "github": "GitHub",
        "website": "Sitio web",
        "portfolio": "Portafolio",
        "other": "Enlace",
    },
    "en": {
        "linkedin": "LinkedIn",
        "github": "GitHub",
        "website": "Website",
        "portfolio": "Portfolio",
        "other": "Link",
    },
}
# ISO-3166 alpha-2 → (es, en). LatAm, Spain, US and main countries.
COUNTRY_NAMES: dict[str, tuple[str, str]] = {
    "AR": ("Argentina", "Argentina"),
    "BO": ("Bolivia", "Bolivia"),
    "BR": ("Brasil", "Brazil"),
    "CL": ("Chile", "Chile"),
    "CO": ("Colombia", "Colombia"),
    "CR": ("Costa Rica", "Costa Rica"),
    "CU": ("Cuba", "Cuba"),
    "DO": ("República Dominicana", "Dominican Republic"),
    "EC": ("Ecuador", "Ecuador"),
    "SV": ("El Salvador", "El Salvador"),
    "GT": ("Guatemala", "Guatemala"),
    "HN": ("Honduras", "Honduras"),
    "MX": ("México", "Mexico"),
    "NI": ("Nicaragua", "Nicaragua"),
    "PA": ("Panamá", "Panama"),
    "PY": ("Paraguay", "Paraguay"),
    "PE": ("Perú", "Peru"),
    "PR": ("Puerto Rico", "Puerto Rico"),
    "UY": ("Uruguay", "Uruguay"),
    "VE": ("Venezuela", "Venezuela"),
    "ES": ("España", "Spain"),
    "US": ("Estados Unidos", "United States"),
    "CA": ("Canadá", "Canada"),
    "GB": ("Reino Unido", "United Kingdom"),
    "IE": ("Irlanda", "Ireland"),
    "DE": ("Alemania", "Germany"),
    "FR": ("Francia", "France"),
    "IT": ("Italia", "Italy"),
    "PT": ("Portugal", "Portugal"),
    "NL": ("Países Bajos", "Netherlands"),
    "BE": ("Bélgica", "Belgium"),
    "CH": ("Suiza", "Switzerland"),
    "AT": ("Austria", "Austria"),
    "SE": ("Suecia", "Sweden"),
    "NO": ("Noruega", "Norway"),
    "DK": ("Dinamarca", "Denmark"),
    "FI": ("Finlandia", "Finland"),
    "PL": ("Polonia", "Poland"),
    "AU": ("Australia", "Australia"),
    "NZ": ("Nueva Zelanda", "New Zealand"),
    "JP": ("Japón", "Japan"),
    "CN": ("China", "China"),
    "IN": ("India", "India"),
    "KR": ("Corea del Sur", "South Korea"),
    "IL": ("Israel", "Israel"),
    "AE": ("Emiratos Árabes Unidos", "United Arab Emirates"),
}

Entry = dict[str, Any]


@lru_cache
def load_i18n(lang: str) -> dict[str, Any]:
    """Load ``web/i18n/{lang}.json`` (falls back to Spanish for unknown languages)."""
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        path = I18N_DIR / "es.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def country_name(code: str | None, lang: str) -> str:
    if not code:
        return ""
    names = COUNTRY_NAMES.get(code.upper())
    if names is None:
        return code.upper()
    return names[0] if lang == "es" else names[1]


def _join(*parts: str | None, sep: str = ", ") -> str:
    return sep.join(p for p in parts if p)


def photo_data_uri(asset: AssetOut | None, uploads_dir: Path | None = None) -> str | None:
    """Data URI of the uploaded photo (prefers the ``*_400.jpg`` render version)."""
    if asset is None:
        return None
    folder = uploads_dir or get_settings().uploads_dir
    stem = Path(asset.filename).stem
    candidates = [(folder / f"{stem}_400.jpg", "image/jpeg"), (folder / asset.filename, asset.mime)]
    for path, mime in candidates:
        if path.is_file():
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return None


class _Builder:
    def __init__(self, cv: ResumeOut, profile: ExportProfileOut) -> None:
        self.cv = cv
        self.profile = profile
        self.lang = cv.language
        self.i18n = load_i18n(self.lang)
        self.t: dict[str, str] = dict(self.i18n["t"])
        self.fmt = profile.date_format
        self.dest = profile.destination

    def visible(self, show_in: ShowIn) -> bool:
        return show_in.value in (ShowIn.BOTH.value, self.dest.value)

    def date(self, value: Any) -> str:
        return fmt_date(value, self.fmt, self.lang)

    # ------------------------------------------------------------------ top level

    def basics(self) -> dict[str, Any]:
        b = self.cv.basics
        photo = None
        if self.profile.include_photo and self.dest == Destination.MAIL:
            photo = photo_data_uri(b.photo)
        return {
            "full_name": b.full_name,
            "headline": b.headline,
            "email": b.email,
            "phone": b.phone,
            "phone_display": phone_display(b.phone),
            "location": _join(b.city, b.region, country_name(b.country, self.lang)),
            "summary": b.summary or "",
            "photo_src": photo,
            "initials": initials(b.full_name),
        }

    def links(self) -> list[Entry]:
        labels = LINK_LABELS.get(self.lang, LINK_LABELS["es"])
        return [
            {
                "kind": link.kind.value,
                "label": link.label or labels.get(link.kind.value, ""),
                "url": link.url,
                "display": url_display(link.url),
            }
            for link in sorted(self.cv.links, key=lambda x: x.position)
        ]

    # ------------------------------------------------------------------ sections

    def experience(self) -> list[Entry]:
        entries: list[Entry] = []
        types: dict[str, str] = self.i18n.get("employment_types", {})
        for exp in sorted(self.cv.experiences, key=lambda x: x.position):
            if not self.visible(exp.show_in):
                continue
            if exp.remote:
                location = _join(exp.city, self.t["remote"], sep=" · ")
            else:
                location = _join(exp.city, country_name(exp.country, self.lang))
            achievements = sorted(exp.achievements, key=lambda x: x.position)
            entries.append(
                {
                    "id": exp.id,
                    "role": exp.role,
                    "company": exp.company,
                    "employment_type": exp.employment_type or "",
                    "employment_type_label": (
                        types.get(exp.employment_type, exp.employment_type)
                        if exp.employment_type
                        else ""
                    ),
                    "location": location,
                    "dates": fmt_range(
                        exp.start_date,
                        exp.end_date,
                        fmt=self.fmt,
                        lang=self.lang,
                        open_label=self.t["present"] if exp.is_current else None,
                    ),
                    "description": exp.description or "",
                    "achievements": [a.text for a in achievements if self.visible(a.show_in)],
                    "technologies": list(exp.technologies),
                }
            )
        return entries

    def education(self) -> list[Entry]:
        return [
            {
                "id": edu.id,
                "degree": edu.degree,
                "institution": edu.institution,
                "field": edu.field or "",
                "location": edu.city or "",
                "dates": fmt_range(
                    edu.start_date,
                    edu.end_date,
                    fmt=self.fmt,
                    lang=self.lang,
                    open_label=self.t["in_progress"] if edu.in_progress else None,
                ),
                "in_progress": edu.in_progress,
                "gpa": edu.gpa or "",
                "description": edu.description or "",
            }
            for edu in sorted(self.cv.education, key=lambda x: x.position)
            if self.visible(edu.show_in)
        ]

    def skills(self) -> list[Entry]:
        levels: dict[str, str] = self.i18n["levels"]["skill"]
        years_i18n: dict[str, str] = self.i18n.get("years", {"one": "1", "many": "{n}"})
        entries: list[Entry] = []
        for cat in sorted(self.cv.skill_categories, key=lambda x: x.position):
            skills = [
                {
                    "name": s.name,
                    "level": s.level.value if s.level else None,
                    "level_label": levels.get(s.level.value) if s.level else None,
                    "years": s.years,
                    "years_label": years_label(s.years, years_i18n["one"], years_i18n["many"]),
                }
                for s in sorted(cat.skills, key=lambda x: x.position)
                if self.visible(s.show_in)
            ]
            if skills:
                entries.append(
                    {
                        "id": cat.id,
                        "category": cat.name,
                        "skills": skills,
                        "names": ", ".join(str(s["name"]) for s in skills),
                    }
                )
        return entries

    def projects(self) -> list[Entry]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role or "",
                "description": p.description,
                "url": p.url or "",
                "url_display": url_display(p.url),
                "dates": fmt_range(p.start_date, p.end_date, fmt=self.fmt, lang=self.lang),
                "technologies": list(p.technologies),
            }
            for p in sorted(self.cv.projects, key=lambda x: x.position)
            if self.visible(p.show_in)
        ]

    def certifications(self) -> list[Entry]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "issuer": c.issuer,
                "date": self.date(c.issue_date),
                "expiry": self.date(c.expiry_date),
                "credential_id": c.credential_id or "",
                "url": c.url or "",
                "url_display": url_display(c.url),
            }
            for c in sorted(self.cv.certifications, key=lambda x: x.position)
            if self.visible(c.show_in)
        ]

    def languages(self) -> list[Entry]:
        levels: dict[str, str] = self.i18n["levels"]["language"]
        return [
            {
                "id": lang.id,
                "name": lang.name,
                "level": lang.level.value,
                "level_label": levels.get(lang.level.value, lang.level.value),
            }
            for lang in sorted(self.cv.languages, key=lambda x: x.position)
        ]

    def sections(self, summary: str) -> list[dict[str, Any]]:
        builders: dict[SectionKey, Callable[[], list[Entry]]] = {
            SectionKey.SUMMARY: list,
            SectionKey.EXPERIENCE: self.experience,
            SectionKey.EDUCATION: self.education,
            SectionKey.SKILLS: self.skills,
            SectionKey.PROJECTS: self.projects,
            SectionKey.CERTIFICATIONS: self.certifications,
            SectionKey.LANGUAGES: self.languages,
        }
        titles: dict[str, dict[str, str]] = self.i18n["sections"]
        is_ats = self.dest == Destination.ATS
        result: list[dict[str, Any]] = []
        for ps in sorted(self.profile.sections, key=lambda x: x.position):
            if not ps.visible:
                continue
            key = ps.section
            entries = builders[key]()
            if key == SectionKey.SUMMARY:
                if not summary:
                    continue
            elif not entries:
                continue
            canonical = titles[key.value]
            if ps.title_override:
                title = ps.title_override.upper() if is_ats else ps.title_override
            else:
                title = canonical["upper"] if is_ats else canonical["title"]
            result.append({"key": key.value, "title": title, "entries": entries})
        return result


def build_context(
    cv: ResumeOut, profile: ExportProfileOut, *, for_preview: bool = False
) -> dict[str, Any]:
    """Template context for ``render/templates/{destination}/base.html``."""
    b = _Builder(cv, profile)
    basics = b.basics()
    sections = b.sections(basics["summary"])
    suffix = DOC_TITLE_SUFFIX.get(cv.language, DOC_TITLE_SUFFIX["es"])
    return {
        "lang": cv.language,
        "destination": profile.destination.value,
        "for_preview": for_preview,
        "doc_title": f"{basics['full_name']} — {suffix}" if basics["full_name"] else suffix,
        "profile": {
            "name": profile.name,
            "theme": profile.theme,
            "accent_color": profile.accent_color,
            "density": profile.density.value,
            "font_family": profile.font_family,
            "include_photo": profile.include_photo,
            "max_pages": profile.max_pages,
        },
        "t": b.t,
        "basics": basics,
        "links": b.links(),
        "sections": sections,
        "sections_by_key": {s["key"]: s for s in sections},
    }
