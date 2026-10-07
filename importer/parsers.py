"""Heuristic parsers: sections → ``ImportPreview`` (spec §11). Never touches the database."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from importer.dates import DateRange, cut, find_date, find_range
from importer.lines import Line
from importer.sectionizer import Kind, Section, body_font_size, sectionize
from importer.text import (
    EMAIL_RE,
    PAGE_FOOTER_RE,
    PHONE_RE,
    URL_RE,
    collapse,
    fix_case,
    fold,
    is_bullet_text,
    normalize_url,
    split_label,
    split_list,
    strip_bullet,
)
from models.enums import DegreeLevel, LanguageLevel, LinkKind
from render.context import COUNTRY_NAMES
from schemas.common import normalize_phone
from schemas.importer import (
    ImportedBasics,
    ImportedCertification,
    ImportedEducation,
    ImportedExperience,
    ImportedLanguage,
    ImportedLink,
    ImportedProject,
    ImportedSkillCategory,
    ImportedText,
    ImportPreview,
    ScoredBool,
    ScoredDate,
    ScoredDegree,
    ScoredLanguageLevel,
    ScoredList,
    ScoredOptStr,
    ScoredStr,
    SectionInfo,
)

COUNTRIES: dict[str, str] = {
    fold(name): code for code, names in COUNTRY_NAMES.items() for name in names
}
REMOTE_WORDS = {"remoto", "remote", "teletrabajo", "trabajo remoto", "home office"}
TECH_LABELS = {"tecnologias", "technologies", "stack", "herramientas", "tools",
               "tecnologias utilizadas", "tech stack"}  # fmt: skip
GPA_LABELS = {"promedio", "gpa", "nota", "calificacion", "promedio acumulado"}
INSTITUTION_WORDS = ("universidad", "university", "instituto", "institute", "college",
                     "escuela", "school", "colegio", "politecnico", "sena", "fundacion",
                     "academia", "academy", "corporacion")  # fmt: skip
_TITLE_SEPARATORS = ((" — ", 0.92), (" | ", 0.85), (" – ", 0.85), (" - ", 0.8), (" @ ", 0.8))
_DURATION_RE = re.compile(r"\([^)]*?(?:año|mes|year|month|yr|mo)[^)]*\)", re.I)
_EXPIRY_RE = re.compile(
    r"(?:vence|vencimiento|expira|expires|expiration|v[aá]lid[oa]?\s+hasta|valid\s+until)"
    r"\s*:?\s*(\S+(?:\s+(?:de\s+)?\d{4})?)",
    re.I,
)
_CREDENTIAL_RE = re.compile(
    r"\b(?:credencial|credential(?:\s+id)?|id)\s*:\s*([A-Za-z0-9][A-Za-z0-9\-_.]*)", re.I
)
_CEFR_RE = re.compile(r"\b([ABC][12])\b")
_LANGUAGE_WORDS: tuple[tuple[tuple[str, ...], LanguageLevel], ...] = (
    (("nativo", "nativa", "native", "lengua materna", "bilingue", "bilingual", "mother tongue"),
     LanguageLevel.NATIVE),
    (("full professional", "dominio", "proficient", "experto"), LanguageLevel.C2),
    (("professional working", "avanzado", "advanced", "fluido", "fluent"), LanguageLevel.C1),
    (("intermedio alto", "upper intermediate", "upper-intermediate"), LanguageLevel.B2),
    (("limited working", "intermedio", "intermediate", "conversacional"), LanguageLevel.B1),
    (("basico", "basic", "elementary", "elemental"), LanguageLevel.A2),
    (("principiante", "beginner"), LanguageLevel.A1),
)  # fmt: skip
_DEGREE_WORDS: tuple[tuple[tuple[str, ...], DegreeLevel], ...] = (
    (("doctorado", "phd", "ph.d", "doctor"), DegreeLevel.PHD),
    (("maestria", "master", "magister", "msc", "mba"), DegreeLevel.MASTER),
    (("especializacion", "especialista", "specialization"), DegreeLevel.SPECIALIZATION),
    (("tecnologo", "tecnologia en"), DegreeLevel.TECHNOLOGIST),
    (("tecnico", "technician"), DegreeLevel.TECHNICAL),
    (("curso", "diplomado", "bootcamp", "course", "certificado"), DegreeLevel.COURSE),
    (("ingenieria", "licenciatura", "pregrado", "bachelor", "profesional en", "grado en",
      "administracion", "economia", "derecho", "psicologia"), DegreeLevel.BACHELOR),
)  # fmt: skip


@dataclass
class Item:
    header: list[Line]
    body: list[Line] = field(default_factory=list)

    @property
    def title(self) -> str:
        return collapse(" ".join(line.text for line in self.header))


# ------------------------------------------------------------------------------ helpers


def _is_bullet(line: Line) -> bool:
    return line.bullet or is_bullet_text(line.text)


def _clean_meta(text: str) -> str:
    text = _DURATION_RE.sub(" ", text).replace("()", " ")
    return collapse(text).strip(" ·|,-–—()")


def country_code(text: str) -> str | None:
    value = text.strip(" .")
    if re.fullmatch(r"[A-Z]{2}", value) and value in COUNTRY_NAMES:
        return value
    return COUNTRIES.get(fold(value))


def parse_location(text: str) -> tuple[str | None, str | None, str | None, bool]:
    """``"Bogotá, Cundinamarca, Colombia · Remoto"`` → (city, region, country, remote)."""
    parts = [p.strip(" ,-–") for p in re.split(r"\s*[·|]\s*", text) if p.strip(" ,-–")]
    remote = any(fold(p) in REMOTE_WORDS for p in parts)
    places = [p for p in parts if fold(p) not in REMOTE_WORDS]
    if not places:
        return None, None, None, remote
    pieces = [p.strip() for p in places[0].split(",") if p.strip()]
    country = country_code(pieces[-1]) if pieces else None
    if country and len(pieces) == 1:
        return None, None, country, remote
    if country:
        pieces = pieces[:-1]
    city = pieces[0] if pieces else None
    region = pieces[1] if len(pieces) > 1 else None
    return city, region, country, remote


def _looks_like_location(text: str) -> bool:
    city, _, country, remote = parse_location(text)
    words = text.split()
    return bool(country or remote) or ("," in text and len(words) <= 6 and city is not None)


def split_title(text: str) -> tuple[str, str, float]:
    """``"Cargo — Empresa"`` → ("Cargo", "Empresa", confidence)."""
    for separator, confidence in _TITLE_SEPARATORS:
        if separator in text:
            left, right = text.split(separator, 1)
            return left.strip(), right.strip(), confidence
    match = re.match(r"^(.+)\s+(?:en|at)\s+(.+)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip(), 0.7
    return text.strip(), "", 0.5


def _cased(text: str, confidence: float) -> tuple[str, float]:
    fixed, changed = fix_case(text)
    return fixed, round(confidence - 0.15, 2) if changed else confidence


def _date_fields(dates: DateRange | None) -> tuple[ScoredDate, ScoredDate, ScoredBool]:
    if dates is None:
        return ScoredDate(), ScoredDate(), ScoredBool()
    conf = dates.confidence
    return (
        ScoredDate(value=dates.start, confidence=conf),
        ScoredDate(value=dates.end, confidence=conf),
        ScoredBool(value=dates.current, confidence=conf),
    )


def split_items(lines: list[Line]) -> list[Item]:
    """Group lines into items.

    Mode A (bold titles, e.g. PDFs/DOCX from cv-ats or LinkedIn): each bold line starts an item.
    Mode B (plain text): date-range lines are anchors; the title is up to 2 lines above.
    Without dates, every non-bullet line is an item (certifications/education lists).
    """

    def is_title(line: Line) -> bool:
        return line.bold and not _is_bullet(line) and split_label(line.text) is None

    if any(is_title(line) for line in lines):
        items: list[Item] = []
        current: Item | None = None
        for line in lines:
            if is_title(line):
                if current is not None and not current.body:
                    current.header.append(line)
                else:
                    current = Item([line])
                    items.append(current)
            elif current is not None:
                current.body.append(line)
        return items

    anchors = [i for i, ln in enumerate(lines) if not _is_bullet(ln) and find_range(ln.text)]
    if not anchors:
        return [Item([ln]) for ln in lines if not _is_bullet(ln)]
    bounds: list[tuple[int, int]] = []
    floor = 0
    for anchor in anchors:
        start = anchor
        while start - 1 >= floor and anchor - (start - 1) <= 2:
            candidate = lines[start - 1]
            text = candidate.text.strip()
            if (
                _is_bullet(candidate)
                or find_range(text)
                or (text.endswith((".", ";")) and len(text.split()) > 8)
                or text[:1].islower()
                or split_label(text) is not None
            ):
                break
            start -= 1
        bounds.append((start, anchor))
        floor = anchor + 1
    result: list[Item] = []
    for k, (start, anchor) in enumerate(bounds):
        end = bounds[k + 1][0] if k + 1 < len(bounds) else len(lines)
        header = lines[start:anchor]
        body = lines[anchor:end] if header else lines[anchor + 1 : end]
        result.append(Item(header or [lines[anchor]], body))
    return result


@dataclass
class _Body:
    description: list[str] = field(default_factory=list)
    achievements: list[list[str]] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


def _body(lines: list[Line]) -> _Body:
    body = _Body()
    current: list[str] | None = None
    bullet_x = 0.0
    for line in lines:
        text = line.text.strip()
        if _is_bullet(line):
            current = [strip_bullet(text)]
            body.achievements.append(current)
            bullet_x = line.x0
            continue
        label = split_label(text)
        if label is not None:
            current = None
            key = fold(label[0])
            if key in TECH_LABELS:
                body.technologies += split_list(label[1])
            else:
                body.labels[key] = label[1]
            continue
        if current is not None and (line.x0 > bullet_x + 1 or text[:1].islower()):
            current.append(text)
            continue
        current = None
        body.description.append(text)
    return body


def _date_line(item: Item) -> tuple[int | None, str, DateRange | None]:
    """Index in ``item.body`` (None if the dates are in the title), text and range."""
    for index, line in enumerate(item.body):
        if not _is_bullet(line) and (dates := find_range(line.text)):
            return index, line.text, dates
    if dates := find_range(item.title):
        return None, item.title, dates
    return None, "", None


# ------------------------------------------------------------------------------ sections


def parse_experience(item: Item) -> ImportedExperience | None:
    index, date_text, dates = _date_line(item)
    title = (
        item.title
        if index is not None or dates is None
        else _clean_meta(cut(item.title, dates.span))
    )
    role, company, confidence = split_title(title)
    body = item.body
    before = body[:index] if index is not None else []
    after = body[index + 1 :] if index is not None else list(body)
    pre = [ln.text.strip() for ln in before if not _is_bullet(ln) and split_label(ln.text) is None]
    if not company and pre:  # LinkedIn: company (bold) then role, then dates
        company, role, confidence = title, pre[0], 0.8
    if not role and not company:
        return None
    remainder = _clean_meta(cut(date_text, dates.span)) if dates and index is not None else ""
    location_conf = 0.85
    if not remainder and after and not _is_bullet(after[0]) and _looks_like_location(after[0].text):
        remainder, after, location_conf = after[0].text, after[1:], 0.7
    city, _, country, remote = parse_location(remainder) if remainder else (None, None, None, False)
    parsed = _body(after)
    start, end, current = _date_fields(dates)
    role_text, role_conf = _cased(role, confidence)
    company_text, company_conf = _cased(company, confidence)
    description = collapse(" ".join(parsed.description))
    return ImportedExperience(
        role=ScoredStr(value=role_text, confidence=role_conf),
        company=ScoredStr(value=company_text, confidence=company_conf if company else 0.2),
        city=ScoredOptStr(value=city, confidence=location_conf if city else 0.0),
        country=ScoredOptStr(value=country, confidence=location_conf if country else 0.0),
        remote=ScoredBool(value=remote, confidence=location_conf if remainder else 0.5),
        start_date=start,
        end_date=end,
        is_current=current,
        description=ScoredOptStr(
            value=description or None,
            confidence=(0.8 if len(parsed.description) <= 2 else 0.7) if description else 0.0,
        ),
        achievements=[
            ImportedText(text=collapse(" ".join(a)), confidence=0.9) for a in parsed.achievements
        ],
        technologies=ScoredList(
            value=parsed.technologies, confidence=0.9 if parsed.technologies else 0.0
        ),
    )


def degree_level(text: str) -> DegreeLevel | None:
    folded = fold(text)
    for words, level in _DEGREE_WORDS:
        if any(word in folded for word in words):
            return level
    return None


def _is_institution(text: str) -> bool:
    folded = fold(text)
    return any(word in folded for word in INSTITUTION_WORDS)


def parse_education(item: Item) -> ImportedEducation | None:
    index, date_text, dates = _date_line(item)
    title = (
        item.title
        if index is not None or dates is None
        else _clean_meta(cut(item.title, dates.span))
    )
    left, right, confidence = split_title(title)
    degree, institution, field_text = left, right, None
    city = None
    remainder = _clean_meta(cut(date_text, dates.span)) if dates and index is not None else ""
    if right:
        if _is_institution(left) and not _is_institution(right):
            degree, institution = right, left
        confidence = 0.9 if confidence >= 0.9 or _is_institution(institution) else 0.75
        if remainder:
            city = parse_location(remainder)[0] or remainder
    elif remainder or (item.body and not _is_bullet(item.body[0])):
        # LinkedIn: institution (bold) + "Degree, Field · (2011 - 2016)"
        institution = title
        detail = remainder or item.body[0].text
        degree, _, field_part = detail.partition(",")
        degree, field_text = degree.strip(" ·"), (field_part.strip(" ·") or None)
        confidence = 0.75
    if not degree and not institution:
        return None
    parsed = _body(item.body[index + 1 :] if index is not None else item.body)
    gpa = next((v for k, v in parsed.labels.items() if k in GPA_LABELS), None)
    start, end, current = _date_fields(dates)
    level = degree_level(degree)
    degree_text, degree_conf = _cased(degree, confidence)
    institution_text, institution_conf = _cased(institution, confidence)
    return ImportedEducation(
        degree=ScoredStr(value=degree_text, confidence=degree_conf),
        institution=ScoredStr(
            value=institution_text, confidence=institution_conf if institution else 0.2
        ),
        level=ScoredDegree(value=level, confidence=0.6 if level else 0.0),
        field=ScoredOptStr(value=field_text, confidence=0.6 if field_text else 0.0),
        city=ScoredOptStr(value=city, confidence=0.85 if city else 0.0),
        start_date=start,
        end_date=end,
        in_progress=current,
        gpa=ScoredOptStr(value=gpa, confidence=0.9 if gpa else 0.0),
    )


def parse_project(item: Item) -> ImportedProject | None:
    index, date_text, dates = _date_line(item)
    name, role, confidence = split_title(item.title)
    if not name:
        return None
    url = None
    rest = item.body[index + 1 :] if index is not None else item.body
    if index is not None:
        meta = cut(date_text, dates.span) if dates else date_text
        if match := URL_RE.search(meta):
            url = match.group(0)
    parsed = _body(rest)
    lines = parsed.description + [" ".join(a) for a in parsed.achievements]
    if url is None:
        for i, text in enumerate(lines):
            match = URL_RE.fullmatch(text.strip())
            if match:
                url = match.group(0)
                lines.pop(i)
                break
    start, end, _ = _date_fields(dates)
    description = collapse(" ".join(lines))
    return ImportedProject(
        name=ScoredStr(value=name, confidence=max(confidence, 0.8)),
        role=ScoredOptStr(value=role or None, confidence=confidence if role else 0.0),
        description=ScoredStr(value=description, confidence=0.85 if description else 0.0),
        url=ScoredOptStr(
            value=normalize_url(url) if url else None, confidence=0.85 if url else 0.0
        ),
        start_date=start,
        end_date=end,
        technologies=ScoredList(
            value=parsed.technologies, confidence=0.9 if parsed.technologies else 0.0
        ),
    )


def parse_certification(item: Item) -> ImportedCertification | None:
    name, issuer, confidence = item.title, "", 0.5
    for separator, conf in ((" — ", 0.92), (" | ", 0.85)):
        if separator in item.title:
            name, issuer = (part.strip() for part in item.title.split(separator, 1))
            confidence = conf
            break
    if not name:
        return None
    meta = " · ".join(line.text for line in item.body)
    expiry = credential = url = None
    if match := _EXPIRY_RE.search(meta):
        found = find_date(match.group(1))
        expiry = found[0] if found else None
        meta = cut(meta, match.span())
    if match := _CREDENTIAL_RE.search(meta):
        credential = match.group(1).rstrip(".·")
        meta = cut(meta, match.span())
    issued = find_date(meta)
    if issued is not None:
        meta = cut(meta, issued[2])
    if match := URL_RE.search(meta):
        url = normalize_url(match.group(0))
    date_conf = issued[1] if issued else 0.0
    return ImportedCertification(
        name=ScoredStr(value=name, confidence=max(confidence, 0.8) if issuer else 0.7),
        issuer=ScoredStr(value=issuer, confidence=confidence if issuer else 0.2),
        issue_date=ScoredDate(value=issued[0] if issued else None, confidence=date_conf),
        expiry_date=ScoredDate(value=expiry, confidence=0.9 if expiry else 0.0),
        credential_id=ScoredOptStr(value=credential, confidence=0.9 if credential else 0.0),
        url=ScoredOptStr(value=url, confidence=0.85 if url else 0.0),
    )


def parse_skills(section: Section) -> list[ImportedSkillCategory]:
    categories: list[ImportedSkillCategory] = []
    loose: list[str] = []
    for line in section.lines:
        text = strip_bullet(line.text) if _is_bullet(line) else line.text.strip()
        label = split_label(text)
        if label is not None:
            skills = split_list(label[1])
            if skills:
                categories.append(ImportedSkillCategory(
                    name=ScoredStr(value=label[0], confidence=0.9),
                    skills=[ImportedText(text=s, confidence=0.9) for s in skills],
                ))  # fmt: skip
            continue
        loose += split_list(text)
    if loose:
        title = section.title.strip().rstrip(":")
        name = title[:1].upper() + title[1:].lower() if title.isupper() else title
        categories.append(ImportedSkillCategory(
            name=ScoredStr(value=name or "Habilidades", confidence=0.6),
            skills=[ImportedText(text=s, confidence=0.8) for s in dict.fromkeys(loose)],
        ))  # fmt: skip
    return categories


def language_level(text: str) -> tuple[LanguageLevel | None, float]:
    if match := _CEFR_RE.search(text.upper()):
        return LanguageLevel(match.group(1)), 0.95
    folded = fold(text)
    for words, level in _LANGUAGE_WORDS:
        if any(word in folded for word in words):
            return level, 0.9 if level is LanguageLevel.NATIVE else 0.75
    return None, 0.0


def parse_languages(section: Section) -> list[ImportedLanguage]:
    result: list[ImportedLanguage] = []
    for line in section.lines:
        text = strip_bullet(line.text) if _is_bullet(line) else line.text.strip()
        match = re.match(r"^(?P<name>[^:(\-—–]+?)\s*(?:[:(\-—–]\s*(?P<rest>.*))?$", text)
        if not match:
            continue
        name, rest = match.group("name").strip(), (match.group("rest") or "").strip(" )")
        level, confidence = language_level(rest or text)
        if not rest and level is not None:  # "Francés básico"
            name = " ".join(w for w in name.split() if language_level(w)[0] is None) or name
        name = name[:1].upper() + name[1:]
        if len(name) > 40 or not name.replace(" ", "").isalpha():
            continue
        level_value = level or LanguageLevel.B1
        result.append(ImportedLanguage(
            name=ScoredStr(value=name, confidence=0.9 if rest or level else 0.6),
            level=ScoredLanguageLevel(value=level_value, confidence=confidence or 0.3),
        ))  # fmt: skip
    return result


# ------------------------------------------------------------------------------ header


def _link_kind(url: str) -> LinkKind:
    lowered = url.lower()
    if "linkedin.com" in lowered:
        return LinkKind.LINKEDIN
    if "github.com" in lowered:
        return LinkKind.GITHUB
    return LinkKind.WEBSITE


def _contact_like(text: str) -> bool:
    without_email = EMAIL_RE.sub(" ", text)
    return bool(EMAIL_RE.search(text) or URL_RE.search(without_email) or _phone_digits(text))


def _phone_digits(text: str) -> str | None:
    for match in PHONE_RE.finditer(text):
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        if (raw.startswith("+") and len(digits) >= 8) or 10 <= len(digits) <= 15:
            return raw
    return None


def parse_header(
    sections: list[Section], body_size: float
) -> tuple[ImportedBasics, list[ImportedLink]]:
    header = [ln for s in sections if s.kind is Kind.HEADER for ln in s.lines]
    contact = [ln for s in sections if s.kind is Kind.CONTACT for ln in s.lines]
    main = [ln for ln in header if ln.column == "main"] or header
    basics = ImportedBasics()
    name_line: Line | None = None
    headline_line: Line | None = None
    consumed: list[int] = []
    if main:
        titled = [ln for ln in main if ln.style == "Title"]
        biggest = max(main[:6], key=lambda ln: ln.size)
        if titled:
            name_line, confidence = titled[0], 0.95
        elif biggest.size >= body_size + 2:
            name_line, confidence = biggest, 0.92
        else:
            name_line, confidence = main[0], 0.6
        following = main[main.index(name_line) + 1 :]
        name_parts = [name_line.text.strip()]
        while following and following[0].size and abs(following[0].size - name_line.size) < 0.5:
            extra = following.pop(0)
            consumed.append(id(extra))
            name_parts.append(extra.text.strip())
        name, confidence = _cased(" ".join(name_parts), confidence)
        basics.full_name = ScoredStr(value=name, confidence=confidence)
        headline_line = next((ln for ln in following[:2] if not _contact_like(ln.text)), None)
        if headline_line is not None and len(headline_line.text) <= 160:
            basics.headline = ScoredStr(value=headline_line.text.strip(), confidence=0.85)
    skip = {id(name_line), id(headline_line), *consumed}
    pool = [ln for ln in header + contact if id(ln) not in skip]
    text = " | ".join(ln.text for ln in pool)
    emails = EMAIL_RE.findall(text)
    if emails:
        basics.email = ScoredStr(value=emails[0], confidence=0.95)
    segments = [s.strip() for s in re.split(r"\s*[|·]\s*", EMAIL_RE.sub(" | ", text)) if s.strip()]
    location = None
    for segment in segments:
        value = (split_label(segment) or ("", segment))[1]
        if URL_RE.search(value) or _phone_digits(value) or not re.search(r"[A-Za-zÁ-ú]", value):
            continue
        if _looks_like_location(value):
            location = value
            break
    if location:
        city, region, country, _ = parse_location(location)
        conf = 0.85 if country else 0.6
        basics.city = ScoredStr(value=city or "", confidence=conf if city else 0.0)
        basics.region = ScoredOptStr(value=region, confidence=conf if region else 0.0)
        basics.country = ScoredOptStr(value=country, confidence=conf if country else 0.0)
    raw_phone = _phone_digits(text)
    if raw_phone:
        try:
            phone = normalize_phone(raw_phone, basics.country.value or "CO")
            basics.phone = ScoredStr(value=phone, confidence=0.9)
        except ValueError:
            basics.phone = ScoredStr(value=raw_phone.strip(), confidence=0.3)
    links: list[ImportedLink] = []
    seen: set[LinkKind] = set()
    for match in URL_RE.finditer(EMAIL_RE.sub(" ", text)):
        url = normalize_url(match.group(0))
        kind = _link_kind(url)
        if kind in seen and kind is not LinkKind.WEBSITE:
            continue
        seen.add(kind)
        links.append(ImportedLink(kind=kind, url=url, confidence=0.9))
    return basics, links


# ------------------------------------------------------------------------------ entry point


def build_preview(lines: list[Line], *, source: str, filename: str | None = None) -> ImportPreview:
    lines = [ln for ln in lines if ln.text.strip() and not PAGE_FOOTER_RE.match(ln.text.strip())]
    preview = ImportPreview(source="docx" if source == "docx" else "pdf", filename=filename)
    if not lines:
        preview.warnings.append(
            "El documento no tiene texto extraíble (¿es un escaneo o una imagen?)."
        )
        return preview
    sections = sectionize(lines)
    body_size = body_font_size(lines)
    preview.basics, preview.links = parse_header(sections, body_size)
    for section in sections:
        preview.sections.append(SectionInfo(
            kind=section.kind.value, title=section.title,
            confidence=section.confidence, lines=len(section.lines),
        ))  # fmt: skip
        kind = section.kind
        if kind is Kind.SUMMARY:
            summary = collapse(" ".join(ln.text for ln in section.lines))
            if summary:
                preview.basics.summary = ScoredOptStr(value=summary, confidence=0.9)
        elif kind is Kind.EXPERIENCE:
            preview.experiences += _items(section, parse_experience)
        elif kind is Kind.EDUCATION:
            preview.education += _items(section, parse_education)
        elif kind is Kind.PROJECTS:
            preview.projects += _items(section, parse_project)
        elif kind is Kind.CERTIFICATIONS:
            preview.certifications += _items(section, parse_certification)
        elif kind is Kind.SKILLS:
            preview.skill_categories += parse_skills(section)
        elif kind is Kind.LANGUAGES:
            preview.languages += parse_languages(section)
        elif kind is Kind.OTHER:
            preview.warnings.append(f"Sección no reconocida: «{section.title}»")
            preview.unassigned += [ln.text for ln in section.lines]
    found = {s.kind for s in sections}
    for kind, label in ((Kind.EXPERIENCE, "experiencia"), (Kind.EDUCATION, "educación")):
        if kind not in found:
            preview.warnings.append(f"No se encontró la sección de {label}.")
    if not preview.basics.email.value:
        preview.warnings.append("No se encontró el correo electrónico.")
    return preview


def _items[T](section: Section, parser: Callable[[Item], T | None]) -> list[T]:
    results: list[T] = []
    for item in split_items(section.lines):
        parsed = parser(item)
        if parsed is not None:
            results.append(parsed)
    return results
