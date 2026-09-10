"""In-memory builders of ``ResumeOut`` / ``ExportProfileOut`` / ``PdfInfo`` for rule tests (no DB).

``make_cv()`` passes every rule in both destinations (with ``make_profile(dest)``,
``GOOD_PDF`` and ``pages=2``); tests mutate one thing at a time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models.enums import SectionKey
from schemas import ExportProfileOut, ResumeOut
from validator.engine import run
from validator.registry import get_rule
from validator.types import Finding, PdfInfo, RuleContext

NOW = datetime(2026, 1, 1, 12, 0, 0)
FULL_NAME = "Ana María Gómez Ruiz"
SUMMARY = (
    "Ingeniera de software con 7 años de experiencia construyendo APIs y plataformas de datos "
    "para comercio electrónico y banca. Especialista en Python, PostgreSQL y AWS, con foco en "
    "calidad, observabilidad y entrega continua. Lidera equipos pequeños y acompaña a perfiles "
    "junior."
)
GOOD_ACHIEVEMENTS = (
    ("Lideré la migración de 3 servicios a Kubernetes, reduciendo 40% los costos.", "40%"),
    ("Diseñé una API de pagos que procesa 2 millones de transacciones al mes.", None),
    ("Automaticé los despliegues con GitHub Actions y bajé la entrega a 1 día.", None),
    ("Implementé pruebas automatizadas que elevaron la cobertura del 30% al 85%.", None),
)
GOOD_PDF = PdfInfo(
    pages=2,
    coverage=0.99,
    has_text=True,
    email_found=True,
    phone_found=True,
    fonts=("ArialMT",),
    fonts_embedded=True,
    title=f"{FULL_NAME} — Hoja de vida",
    author=FULL_NAME,
    filename="Ana_Gomez_CV_ats.pdf",
)


def ach(aid: int, text: str, metric: str | None = None, show_in: str = "both") -> dict[str, Any]:
    return {"id": aid, "text": text, "metric_value": metric, "show_in": show_in, "position": aid}


def exp(eid: int, **kw: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": eid,
        "company": f"Empresa {eid}",
        "role": "Ingeniera Backend",
        "employment_type": "full-time",
        "city": "Bogotá",
        "country": "CO",
        "remote": False,
        "start_date": "2018-01-01",
        "end_date": "2021-12-01",
        "is_current": False,
        "description": None,
        "show_in": "both",
        "position": eid,
        "achievements": [
            ach(eid * 10 + i, text, metric) for i, (text, metric) in enumerate(GOOD_ACHIEVEMENTS)
        ],
        "technologies": ["Python", "AWS"],
    }
    data.update(kw)
    return data


def edu(eid: int, **kw: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": eid,
        "institution": "Universidad Nacional",
        "degree": "Ingeniería de Sistemas",
        "level": "bachelor",
        "field": None,
        "city": "Bogotá",
        "start_date": "2012-01-01",
        "end_date": "2017-06-01",
        "in_progress": False,
        "gpa": None,
        "description": None,
        "show_in": "both",
        "position": eid,
    }
    data.update(kw)
    return data


def skill(sid: int, name: str, show_in: str = "both") -> dict[str, Any]:
    return {
        "id": sid,
        "name": name,
        "level": "advanced",
        "years": 3,
        "technology_id": None,
        "show_in": show_in,
        "position": sid,
    }


def category(cid: int, name: str, names: list[str]) -> dict[str, Any]:
    return {
        "id": cid,
        "name": name,
        "position": cid,
        "skills": [skill(cid * 100 + i, n) for i, n in enumerate(names)],
    }


def make_cv(basics: dict[str, Any] | None = None, **top: Any) -> ResumeOut:
    data: dict[str, Any] = {
        "id": 1,
        "name": "Prueba",
        "language": "es",
        "is_default": True,
        "notes": None,
        "created_at": NOW,
        "updated_at": NOW,
        "basics": {
            "id": 1,
            "full_name": FULL_NAME,
            "headline": "Ingeniera Backend",
            "email": "ana.gomez@example.com",
            "phone": "+573001234567",
            "city": "Bogotá",
            "region": None,
            "country": "CO",
            "summary": SUMMARY,
            "photo_asset_id": 5,
            "photo": None,
        },
        "links": [
            {
                "id": 1,
                "kind": "linkedin",
                "label": "LinkedIn",
                "url": "https://www.linkedin.com/in/ana-gomez",
                "position": 0,
            }
        ],
        "experiences": [
            exp(1, start_date="2022-01-01", end_date=None, is_current=True, position=0),
            exp(2, position=1),
        ],
        "education": [edu(1)],
        "skill_categories": [
            category(1, "Lenguajes", ["Python", "SQL", "Go"]),
            category(2, "Plataforma", ["PostgreSQL", "AWS", "Docker", "Kubernetes"]),
        ],
        "projects": [],
        "certifications": [],
        "languages": [{"id": 1, "name": "Inglés", "level": "C1", "position": 0}],
        "profiles": [],
    }
    data["basics"].update(basics or {})
    data.update(top)
    return ResumeOut.model_validate(data)


def sections(order: list[SectionKey] | None = None, **overrides: Any) -> list[dict[str, Any]]:
    """Profile sections; ``overrides={"experience": {"visible": False}}``."""
    keys = order or list(SectionKey)
    result = []
    for i, key in enumerate(keys):
        row = {"id": 10 + i, "section": key.value, "visible": True, "position": i}
        row["title_override"] = None
        row.update(overrides.get(key.value, {}))
        result.append(row)
    return result


def make_profile(dest: str = "ats", **kw: Any) -> ExportProfileOut:
    ats = dest == "ats"
    data: dict[str, Any] = {
        "id": 1 if ats else 2,
        "resume_id": 1,
        "name": "Plataforma" if ats else "Correo",
        "destination": dest,
        "theme": None if ats else "slate",
        "accent_color": None,
        "density": "normal",
        "include_photo": not ats,
        "max_pages": 2,
        "date_format": "MM/YYYY",
        "font_family": "Arial",
        "sections": sections(),
    }
    data.update(kw)
    return ExportProfileOut.model_validate(data)


def make_ctx(
    dest: str = "ats",
    *,
    cv: ResumeOut | None = None,
    profile: ExportProfileOut | None = None,
    html: str | None = None,
    pages: int | None = 2,
    pdf: PdfInfo | None = None,
) -> RuleContext:
    return RuleContext(
        cv=cv or make_cv(),
        profile=profile or make_profile(dest),
        html=html,
        pages=pages,
        pdf=pdf,
    )


def check(rule_id: str, ctx: RuleContext) -> list[Finding]:
    """Findings of a single rule (severity assigned by the engine)."""
    return list(run(ctx, rules=[get_rule(rule_id)]).findings)


def severities(rule_id: str, ctx: RuleContext) -> set[str]:
    return {f.severity.value for f in check(rule_id, ctx)}
