"""Split lines into sections using a multi-language heading dictionary + layout hints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median

from importer.lines import Line
from importer.text import fold, is_bullet_text


class Kind(StrEnum):
    HEADER = "header"  # lines before the first heading (name, headline, contact)
    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"
    OTHER = "other"  # a heading we do not understand


_HEADINGS: dict[Kind, tuple[str, ...]] = {
    Kind.CONTACT: ("contacto", "contactar", "datos de contacto", "informacion de contacto",
                   "contact", "contact info", "contact information"),
    Kind.SUMMARY: ("resumen", "resumen profesional", "perfil", "perfil profesional", "extracto",
                   "acerca de", "acerca de mi", "sobre mi", "objetivo", "objetivo profesional",
                   "summary", "professional summary", "profile", "about", "about me"),
    Kind.EXPERIENCE: ("experiencia", "experiencia profesional", "experiencia laboral",
                      "historial laboral", "trayectoria", "trayectoria profesional",
                      "experience", "work experience", "professional experience", "employment",
                      "employment history", "work history"),
    Kind.EDUCATION: ("educacion", "formacion", "formacion academica", "estudios",
                     "educacion y formacion", "education", "academic background"),
    Kind.SKILLS: ("habilidades", "habilidades tecnicas", "aptitudes", "aptitudes principales",
                  "competencias", "conocimientos", "conocimientos tecnicos", "skills",
                  "top skills", "technical skills", "tecnologias"),
    Kind.PROJECTS: ("proyectos", "proyectos destacados", "projects", "personal projects"),
    Kind.CERTIFICATIONS: ("certificaciones", "certificados", "cursos y certificaciones",
                          "licencias y certificaciones", "certifications", "certificates",
                          "licenses certifications", "licenses and certifications"),
    Kind.LANGUAGES: ("idiomas", "lenguas", "languages"),
}  # fmt: skip
HEADINGS: dict[str, Kind] = {phrase: kind for kind, items in _HEADINGS.items() for phrase in items}


def heading_key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z ]+", " ", fold(text)).split())


@dataclass
class Section:
    kind: Kind
    title: str
    confidence: float
    column: str
    lines: list[Line] = field(default_factory=list)


def heading_kind(line: Line, body_size: float) -> tuple[Kind, float] | None:
    """Kind and confidence of ``line`` if it is a section heading."""
    text = line.text.strip()
    if line.bullet or is_bullet_text(text) or len(text) > 45:
        return None
    styled = line.style.startswith("Heading 1")
    upper = text.isupper()
    bigger = line.size > body_size + 0.4
    kind = HEADINGS.get(heading_key(text.rstrip(":")))
    if kind is not None:
        confidence = 0.8 + 0.05 * upper + 0.05 * line.bold + 0.05 * bigger + 0.1 * styled
        return kind, round(min(confidence, 0.99), 2)
    words = text.split()
    unknown_heading = line.bold and upper and bigger and 1 <= len(words) <= 4
    if styled or (unknown_heading and not re.search(r"[\d:@]", text)):
        return Kind.OTHER, 0.5
    return None


def body_font_size(lines: list[Line]) -> float:
    sizes = [line.size for line in lines if line.size > 0]
    return float(median(sizes)) if sizes else 0.0


def sectionize(lines: list[Line]) -> list[Section]:
    """Sections in reading order. Each column keeps its own current section."""
    size = body_font_size(lines)
    sections: list[Section] = []
    current: dict[str, Section] = {}
    for line in lines:
        detected = heading_kind(line, size)
        if detected is not None:
            section = Section(detected[0], line.text.strip(), detected[1], line.column)
            sections.append(section)
            current[line.column] = section
            continue
        section_or_none = current.get(line.column)
        if section_or_none is None:
            section_or_none = Section(Kind.HEADER, "", 1.0, line.column)
            sections.append(section_or_none)
            current[line.column] = section_or_none
        section_or_none.lines.append(line)
    return sections
