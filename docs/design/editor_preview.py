"""Prototipo estático del editor (herramienta de Diseño).

Renderiza los templates de ``web/`` con datos que imitan los esquemas ``*Out`` de Backend (se
construyen desde ``sample_context_es.json``) y escribe páginas HTML en ``docs/design/out/editor/``
que enlazan ``static/`` por ruta relativa: se abren con ``file://`` o con cualquier servidor
estático desde la raíz del repo. Las peticiones HTMX no funcionan aquí (no hay servidor); sí el JS
de cliente (Alpine, Sortable, contadores, recorte).

Uso:
    uv run python docs/design/editor_preview.py
"""

from __future__ import annotations

import base64
import json
import re
import sys
from datetime import UTC, date, datetime
from itertools import count
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_sample import Variant, build_context

ROOT = Path(__file__).resolve().parents[2]
DESIGN_DIR = ROOT / "docs" / "design"
OUT_DIR = DESIGN_DIR / "out" / "editor"
WEB_DIR = ROOT / "web"
STATIC_URL = "../../../../static"  # desde docs/design/out/editor/

MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
SECTION_ORDER = (
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "languages",
)


# ------------------------------------------------------------------ filtros (mismos que Backend)


def ym(value: date | None) -> str:
    return f"{value.year:04d}-{value.month:02d}" if value else ""


def mdate(value: date | None) -> str:
    return f"{MONTHS[value.month - 1]} {value.year}" if value else ""


def dt(value: datetime) -> str:
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}, {value:%H:%M}"


def make_env() -> Environment:
    env = Environment(loader=FileSystemLoader(WEB_DIR), autoescape=True)
    env.filters.update(ym=ym, mdate=mdate, dt=dt)
    labels = json.loads((WEB_DIR / "i18n" / "ui_es.json").read_text(encoding="utf-8"))["choices"]
    env.globals["static_url"] = STATIC_URL
    env.globals["choices"] = {
        name: [{"value": value, "label": label} for value, label in block.items()]
        for name, block in labels.items()
    }
    return env


# ------------------------------------------------------------------ datos tipo *Out

_ids = count(100)
_RANGE = re.compile(r"(?:(\d{2})/)?(\d{4})")


def parse_range(text: str) -> tuple[date | None, date | None, bool]:
    """ "03/2022 – Actual" → (2022-03-01, None, True); "2021 – 2022" → (2021-01, 2022-12, False)."""
    found = _RANGE.findall(text)
    if not found:
        return None, None, False
    month, year = found[0]
    start = date(int(year), int(month or 1), 1)
    if len(found) < 2:
        return start, None, True
    month, year = found[1]
    return start, date(int(year), int(month or 12), 1), False


def build_resume(ctx: dict[str, Any], photo: bool) -> dict[str, Any]:
    """Árbol con la forma de ``ResumeOut`` a partir del contexto de render de muestra."""
    s = ctx["sections_by_key"]
    b = ctx["basics"]
    city, region, _country = (part.strip() for part in b["location"].split(","))
    now = datetime(2026, 9, 10, 15, 4, tzinfo=UTC)

    experiences = []
    for pos, e in enumerate(s["experience"]["entries"]):
        start, end, current = parse_range(e["dates"])
        achievements = [
            {
                "id": next(_ids),
                "text": text,
                "metric_value": (re.search(r"\d+(?:[.,]\d+)?\s?%|\d+x", text) or [None])[0],
                "show_in": "mail" if (pos, i) == (0, 4) else "both",
                "position": i,
            }
            for i, text in enumerate(e["achievements"])
        ]
        loc_city = e["location"].split(",")[0].split("·")[0].strip()
        experiences.append(
            {
                "id": e["id"],
                "company": e["company"],
                "role": e["role"],
                "employment_type": e["employment_type"] or None,
                "city": loc_city,
                "country": "CO",
                "remote": "Remoto" in e["location"],
                "start_date": start,
                "end_date": end,
                "is_current": current,
                "description": e["description"] or None,
                "show_in": "both",
                "position": pos,
                "achievements": achievements,
                "technologies": e["technologies"],
            }
        )

    education = []
    for pos, e in enumerate(s["education"]["entries"]):
        start, end, _ = parse_range(e["dates"])
        education.append(
            {
                "id": e["id"],
                "institution": e["institution"],
                "degree": e["degree"],
                "level": "specialization" if pos == 0 else "bachelor",
                "field": e["field"] or None,
                "city": e["location"] or None,
                "start_date": start,
                "end_date": end,
                "in_progress": e["in_progress"],
                "gpa": e["gpa"] or None,
                "description": e["description"] or None,
                "show_in": "both",
                "position": pos,
            }
        )

    categories = [
        {
            "id": c["id"],
            "name": c["category"],
            "position": pos,
            "skills": [
                {
                    "id": next(_ids),
                    "name": k["name"],
                    "level": k["level"],
                    "years": k["years"],
                    "technology_id": None,
                    "show_in": "ats" if k["name"] == "SQL" else "both",
                    "position": i,
                }
                for i, k in enumerate(c["skills"])
            ],
        }
        for pos, c in enumerate(s["skills"]["entries"])
    ]

    projects = []
    for pos, p in enumerate(s["projects"]["entries"]):
        start, end, _ = parse_range(p["dates"])
        projects.append(
            {
                "id": p["id"],
                "name": p["name"],
                "role": p["role"] or None,
                "description": p["description"],
                "url": p["url"] or None,
                "start_date": start,
                "end_date": end if end != start else None,
                "show_in": "both",
                "position": pos,
                "technologies": p["technologies"],
            }
        )

    certifications = []
    for pos, c in enumerate(s["certifications"]["entries"]):
        issue, _, _ = parse_range(c["date"])
        expiry, _, _ = parse_range(c["expiry"])
        certifications.append(
            {
                "id": c["id"],
                "name": c["name"],
                "issuer": c["issuer"],
                "issue_date": issue,
                "expiry_date": expiry,
                "credential_id": c["credential_id"] or None,
                "url": c["url"] or None,
                "show_in": "mail" if pos == 1 else "both",
                "position": pos,
            }
        )

    photo_asset = {"id": 7, "sha256": "ab12cd34" * 8} if photo else None
    return {
        "id": 1,
        "name": "Backend bancario",
        "language": ctx["lang"],
        "is_default": True,
        "notes": None,
        "created_at": now,
        "updated_at": now,
        "basics": {
            "id": 1,
            "full_name": b["full_name"],
            "headline": b["headline"],
            "email": b["email"],
            "phone": b["phone"],
            "city": city,
            "region": region,
            "country": "CO",
            "summary": b["summary"],
            "photo_asset_id": 7 if photo else None,
            "photo": photo_asset,
        },
        "links": [
            {"id": i + 1, "kind": link["kind"], "label": None, "url": link["url"], "position": i}
            for i, link in enumerate(ctx["links"])
        ],
        "experiences": experiences,
        "education": education,
        "skill_categories": categories,
        "projects": projects,
        "certifications": certifications,
        "languages": [
            {"id": x["id"], "name": x["name"], "level": x["level"], "position": i}
            for i, x in enumerate(s["languages"]["entries"])
        ],
    }


def build_profiles() -> list[dict[str, Any]]:
    def sections(hidden: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        return [
            {
                "id": i + 1,
                "section": key,
                "visible": key not in hidden,
                "position": i,
                "title_override": None,
            }
            for i, key in enumerate(SECTION_ORDER)
        ]

    base = {"resume_id": 1, "density": "normal", "max_pages": 2, "date_format": "MM/YYYY"}
    return [
        {
            **base,
            "id": 1,
            "name": "Plataforma",
            "destination": "ats",
            "theme": None,
            "accent_color": None,
            "include_photo": False,
            "font_family": "Arial",
            "sections": sections(),
        },
        {
            **base,
            "id": 2,
            "name": "Correo",
            "destination": "mail",
            "theme": "slate",
            "accent_color": None,
            "include_photo": True,
            "font_family": "Arial",
            "sections": sections(hidden=("certifications",)),
        },
    ]


def sample_report(resume: dict[str, Any]) -> dict[str, Any]:
    exp = resume["experiences"]
    rows = [
        (
            "contact.linkedin_present",
            "info",
            "basics",
            None,
            None,
            "LinkedIn está presente y visible como texto.",
            None,
        ),
        (
            "content.min_achievements",
            "warning",
            "experience",
            "experience",
            exp[2]["id"],
            "«Desarrollador de Software» tiene solo 3 logros.",
            "Agrega al menos un logro más, con un resultado medible.",
        ),
        (
            "content.metric",
            "warning",
            "experience",
            "achievement",
            exp[2]["achievements"][2]["id"],
            "El logro no incluye una métrica.",
            "Cuantifica: %, tiempo, dinero o volumen.",
        ),
        (
            "dates.format_consistent",
            "error",
            "experience",
            "experience",
            exp[1]["id"],
            "La fecha de fin no coincide con el formato del perfil.",
            "Usa MM/AAAA en todas las fechas.",
        ),
        (
            "content.summary_length",
            "info",
            "summary",
            "basics",
            None,
            "El resumen tiene 452 caracteres (ideal 200–600).",
            None,
        ),
        (
            "structure.section_order",
            "warning",
            "profile",
            "profile_section",
            None,
            "Certificaciones aparece antes que Idiomas; revisa el orden recomendado.",
            None,
        ),
    ]
    findings = [
        {
            "id": i + 1,
            "rule_id": r,
            "severity": sev,
            "section": sec,
            "entity": ent,
            "entity_id": eid,
            "message": msg,
            "suggestion": sug,
        }
        for i, (r, sev, sec, ent, eid, msg, sug) in enumerate(rows)
    ]
    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (str(f["section"]), order[f["severity"]]))
    return {
        "id": 1,
        "resume_id": 1,
        "profile_id": 1,
        "score": 78,
        "errors": 1,
        "warnings": 3,
        "created_at": datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
        "findings": findings,
    }


# ------------------------------------------------------------------ páginas


def inject(html: str, marker: str, fragment: str) -> str:
    assert marker in html, marker
    return html.replace(marker, marker + fragment, 1)


def main() -> int:
    env = make_env()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = json.loads((DESIGN_DIR / "sample_context_es.json").read_text(encoding="utf-8"))
    photo_uri = "data:image/png;base64," + base64.b64encode(
        (DESIGN_DIR / "sample_photo.png").read_bytes()
    ).decode("ascii")

    resume = build_resume(base, photo=True)
    profiles = build_profiles()
    resume["profiles"] = profiles
    report = sample_report(resume)
    now = datetime(2026, 9, 10, 15, 4, tzinfo=UTC)
    resumes = [
        {
            "id": 1,
            "name": "Backend bancario",
            "language": "es",
            "is_default": True,
            "notes": "Versión para bancos y fintech.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": 2,
            "name": "General",
            "language": "es",
            "is_default": False,
            "notes": None,
            "created_at": now,
            "updated_at": datetime(2026, 9, 2, 9, 30, tzinfo=UTC),
        },
        {
            "id": 3,
            "name": "Remote US (English)",
            "language": "en",
            "is_default": False,
            "notes": None,
            "created_at": now,
            "updated_at": datetime(2026, 8, 21, 18, 12, tzinfo=UTC),
        },
    ]

    def preview(profile: dict[str, Any]) -> str:
        is_mail = profile["destination"] == "mail"
        variant = Variant("p", profile["destination"], theme=profile["theme"], photo=is_mail)
        ctx = build_context(base, variant)
        ctx["for_preview"] = True
        tpl = env_render.get_template(f"{profile['destination']}/base.html")
        return tpl.render(**ctx)

    env_render = Environment(
        loader=FileSystemLoader(ROOT / "render" / "templates"), autoescape=True
    )

    def editor(profile: dict[str, Any]) -> str:
        # Solo en el prototipo: sin servidor, el disparador "load" del formulario de la barra
        # pediría /ui/.../preview y fallaría; la preview ya viene pintada en el HTML.
        html = env.get_template("editor/index.html").render(
            resume=resume,
            profiles=profiles,
            active_profile=profile,
            density=profile["density"],
            photo_url=photo_uri,
            preview_html=preview(profile),
            pages=2,
            max_pages=profile["max_pages"],
        )
        return html.replace('hx-trigger="load, change', 'hx-trigger="change', 1)

    pages: dict[str, str] = {}
    pages["index.html"] = env.get_template("index.html").render(resumes=resumes)
    pages["index_vacio.html"] = env.get_template("index.html").render(resumes=[])
    pages["editor_ats.html"] = editor(profiles[0])
    pages["editor_mail.html"] = editor(profiles[1])

    panel = env.get_template("partials/validation_panel.html").render(
        report=report, profile=profiles[0], blocked=True
    )
    pages["editor_validacion.html"] = inject(editor(profiles[0]), '<div id="vpanel-slot">', panel)

    modal = env.get_template("partials/export_modal.html").render(
        resume=resume, profiles=profiles, active_profile=profiles[1], report=report
    )
    pages["editor_exportar.html"] = inject(editor(profiles[1]), '<div id="modal-slot">', modal)

    job = {"id": 12, "status": "done", "pages": 2, "roundtrip_ok": True, "error": None}
    files = [
        "Santiago_Restrepo_CV_correo.pdf",
        "Santiago_Restrepo_CV_correo_sinfoto.pdf",
        "Santiago_Restrepo_CV_correo.docx",
    ]
    result = {
        "job": job,
        "files": files,
        "score": 94,
        "errors": 0,
        "warnings": 2,
        "coverage": 0.99,
        "findings": [],
        "downloads": [
            "/api/exports/12/download?format=pdf",
            "/api/exports/12/download?format=pdf&variant=sinfoto",
            "/api/exports/12/download?format=docx",
        ],
    }
    done = env.get_template("partials/export_result.html").render(result=result)
    modal_done = re.sub(
        r'(<div class="modal-body" id="export-body">).*?(</div>\s*<footer)',
        lambda m: m.group(1) + done + m.group(2),
        modal,
        count=1,
        flags=re.S,
    )
    pages["editor_exportado.html"] = inject(
        editor(profiles[1]), '<div id="modal-slot">', modal_done
    )

    # Borrador de experiencia con error de validación (respuesta 422) al final de la lista.
    draft = {k: None for k in resume["experiences"][0]} | {
        "id": None,
        "role": "Líder técnico",
        "company": "",
        "remote": False,
        "is_current": False,
        "show_in": "both",
        "position": 0,
        "achievements": [],
        "technologies": [],
        "start_date": date(2020, 1, 1),
    }
    errors = {
        "company": "Campo obligatorio",
        "end_date": "Indica la fecha de fin o marca la experiencia como actual",
    }
    draft_html = env.get_template("editor/item_experience.html").render(
        item=draft, resume_id=1, errors=errors, open=True
    )
    editing = editor(profiles[0]).replace(
        '<details class="section-acc" id="sec-experience" data-section="experience">',
        '<details class="section-acc" id="sec-experience" data-section="experience" open>',
        1,
    )
    marker = 'id="list-experience" data-sortable data-order-url="/api/resumes/1/experiences/order">'
    pages["editor_error.html"] = inject(editing, marker, draft_html)

    for key in ("ats", "mail"):
        profile = profiles[0] if key == "ats" else profiles[1]
        pages[f"perfiles_{key}.html"] = env.get_template("editor/profiles.html").render(
            resume=resume, profiles=profiles, active_profile=profile
        )

    for name, html in pages.items():
        (OUT_DIR / name).write_bytes(html.encode("utf-8"))
        print(f"{name:<28} {len(html) // 1024:>4} KB")
    print(f"\nSalida en {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
