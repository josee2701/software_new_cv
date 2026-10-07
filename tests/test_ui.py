"""Editor pages and HTMX fragments (``docs/design/EDITOR_CONTEXT.md``, spec §7)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, get_args
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from starlette.datastructures import FormData

from app.db import get_session
from app.main import create_app
from app.routers.ui import SECTION_KEYS, sort_findings
from app.routers.ui_items import SPECS
from app.web import CHOICE_KEYS, WEB_DIR, draft, dt, load_choices, mdate, read_form, ym
from models.enums import (
    DegreeLevel,
    Density,
    Destination,
    ExportFormat,
    LanguageLevel,
    LinkKind,
    SectionKey,
    Severity,
    ShowIn,
    SkillLevel,
)
from schemas.profile import ATS_FONTS, THEMES, DateFormat, ExportProfileCreate
from schemas.validation import FindingOut

TRIGGER = "cv-changed"
FORM_TYPE = {"Content-Type": "application/x-www-form-urlencoded"}


def urlencoded(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """``httpx`` only accepts a dict as ``data``: repeated keys go as raw content."""
    return {"content": urlencode(pairs), "headers": FORM_TYPE}


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def cv(client: TestClient) -> dict[str, Any]:
    """A resume with one item in every collection, plus the ids the fragments need."""
    rid = client.post("/api/resumes", json={"name": "General", "is_default": True}).json()["id"]
    client.put(
        f"/api/resumes/{rid}/basics",
        json={
            "full_name": "Ana María Gómez",
            "headline": "Ingeniera backend",
            "email": "ana@correo.co",
            "phone": "3001234567",
            "city": "Bogotá",
            "country": "CO",
            "summary": "Ingeniera backend con foco en Python.",
        },
    )
    link = client.post(
        f"/api/resumes/{rid}/links", json={"kind": "linkedin", "url": "linkedin.com/in/ana"}
    ).json()
    exp = client.post(
        f"/api/resumes/{rid}/experiences",
        json={"company": "Acme", "role": "Dev", "start_date": "2020-01", "end_date": "2022-03"},
    ).json()
    ach = client.post(
        f"/api/experiences/{exp['id']}/achievements", json={"text": "Reduje el tiempo 30%"}
    ).json()
    edu = client.post(
        f"/api/resumes/{rid}/education", json={"institution": "UNAL", "degree": "Ing. Sistemas"}
    ).json()
    cat = client.post(f"/api/resumes/{rid}/skill-categories", json={"name": "Lenguajes"}).json()
    skill = client.post(
        f"/api/skill-categories/{cat['id']}/skills",
        json={"name": "Python", "level": "expert", "years": 5},
    ).json()
    project = client.post(
        f"/api/resumes/{rid}/projects",
        json={"name": "Agenda", "description": "Aplicación propia de agenda personal."},
    ).json()
    cert = client.post(
        f"/api/resumes/{rid}/certifications", json={"name": "AWS SAA", "issuer": "Amazon"}
    ).json()
    lang = client.post(
        f"/api/resumes/{rid}/languages", json={"name": "Inglés", "level": "B2"}
    ).json()
    profiles = client.get(f"/api/resumes/{rid}/profiles").json()
    return {
        "resume_id": rid,
        "links": link["id"],
        "experiences": exp["id"],
        "achievements": ach["id"],
        "education": edu["id"],
        "skill-categories": cat["id"],
        "skills": skill["id"],
        "projects": project["id"],
        "certifications": cert["id"],
        "languages": lang["id"],
        "ats": profiles[0]["id"],
        "mail": profiles[1]["id"],
    }


# ------------------------------------------------------------------------------ §1 choices


def test_choices_keys_match_enums_and_schemas() -> None:
    """Contract §1: every block of ``choices`` matches the enums / profile schema values."""
    choices = load_choices()
    assert set(choices) == set(CHOICE_KEYS)
    i18n = json.loads((WEB_DIR / "i18n" / "es.json").read_text("utf-8"))
    expected: dict[str, list[str]] = {
        "show_in": [e.value for e in ShowIn],
        "link_kind": [e.value for e in LinkKind],
        "degree_level": [e.value for e in DegreeLevel],
        "skill_level": [e.value for e in SkillLevel],
        "language_level": [e.value for e in LanguageLevel],
        "destination": [e.value for e in Destination],
        "density": [e.value for e in Density],
        "section_key": [e.value for e in SectionKey],
        "export_format": [e.value for e in ExportFormat],
        "theme": list(THEMES),
        "ats_font": list(ATS_FONTS),
        "date_format": list(get_args(DateFormat)),
        "max_pages": [
            str(v) for v in get_args(ExportProfileCreate.model_fields["max_pages"].annotation)
        ],
        # No enum in models/: the labels of the render i18n are the source of truth.
        "employment_type": list(i18n["employment_types"]),
    }
    for name, values in expected.items():
        # El orden lo manda el JSON de la UI; lo que debe coincidir son las claves.
        assert sorted(opt["value"] for opt in choices[name]) == sorted(values), name
        assert all(opt["label"] for opt in choices[name]), name


# ------------------------------------------------------------------------------ §2 helpers


def test_read_form_conventions() -> None:
    """Contract §2.1: absent · ``""`` → None · repeated: last wins · ``formats`` · ``_open``."""
    form = read_form(
        FormData(
            [
                ("remote", "false"),
                ("remote", "true"),
                ("city", ""),
                ("formats", "pdf"),
                ("formats", "docx"),
                ("_open", "1"),
            ]
        )
    )
    assert form.values == {"remote": "true", "city": None, "formats": ["pdf", "docx"]}
    assert form.open is True
    assert "headline" not in form.values
    unchecked = read_form(FormData([("remote", "false"), ("_open", "0")]))
    assert unchecked.values == {"remote": "false"} and unchecked.open is False


def test_filters() -> None:
    from datetime import date, datetime

    assert ym(date(2024, 3, 7)) == "2024-03"
    assert ym(None) == "" and ym("2024-03") == "2024-03"
    assert mdate(date(2024, 3, 1)) == "mar 2024" and mdate(None) == ""
    assert dt(datetime(2026, 9, 10, 15, 4)) == "10 sep 2026, 15:04"


@pytest.mark.parametrize("spec", SPECS, ids=[s.coll for s in SPECS])
def test_draft_has_every_out_key(spec: Any) -> None:
    """Contract §4.3: the draft carries **all** the keys of the ``*Out`` with ``id=None``."""
    item = draft(spec.out, **spec.draft_extra)
    assert set(item) == set(spec.out.model_fields)
    assert item["id"] is None and item["position"] == 0
    if "show_in" in item:
        assert item["show_in"] == ShowIn.BOTH
    for name, info in spec.out.model_fields.items():
        if name in spec.draft_extra:
            continue
        if info.annotation is bool:
            assert item[name] is False, name


def test_language_and_link_drafts_keep_their_defaults(
    client: TestClient, cv: dict[str, Any]
) -> None:
    rid = cv["resume_id"]
    assert 'value="B2" selected' in client.get(f"/ui/resumes/{rid}/languages/new").text
    assert 'value="linkedin" selected' in client.get(f"/ui/resumes/{rid}/links/new").text


# -------------------------------------------------------------------------------- §3 pages


def test_home_lists_resumes(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Mis hojas de vida" in r.text and 'id="resume-list"' in r.text


def test_editor_page_has_toolbar_accordion_and_preview(
    client: TestClient, cv: dict[str, Any]
) -> None:
    r = client.get(f"/resumes/{cv['resume_id']}/edit")
    assert r.status_code == 200
    assert 'id="toolbar"' in r.text  # barra superior (perfil + densidad)
    assert r.text.count('class="section-acc"') == 8  # acordeón completo
    assert 'id="preview-pane"' in r.text and 'id="pages-badge"' in r.text
    assert r.text.count('id="pages-badge"') == 1


def test_editor_page_honours_profile_and_density(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.get(
        f"/resumes/{cv['resume_id']}/edit",
        params={"profile_id": cv["mail"], "density": "compact"},
    )
    assert r.status_code == 200
    assert 'value="compact" selected' in r.text
    bad = client.get(f"/resumes/{cv['resume_id']}/edit", params={"profile_id": 999})
    assert bad.status_code == 404


def test_profiles_page(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.get(f"/resumes/{cv['resume_id']}/profiles", params={"profile_id": cv["mail"]})
    assert r.status_code == 200
    assert 'id="profile-settings"' in r.text and "data-sections-editor" in r.text


# ---------------------------------------------------------------------------- §4.1 CV list


def test_resume_list_actions(client: TestClient, cv: dict[str, Any]) -> None:
    rid = cv["resume_id"]
    r = client.post("/ui/resumes", data={"name": "Nuevo", "language": "es"})
    assert r.status_code == 200 and r.text == ""
    new_id = int(r.headers["hx-redirect"].split("/")[2])

    assert client.post("/ui/resumes", data={"name": "Nuevo"}).status_code == 409

    r = client.post(f"/ui/resumes/{rid}/duplicate")
    assert r.status_code == 200 and r.headers["hx-trigger"] == TRIGGER
    assert 'id="resume-list"' in r.text and "(copia)" in r.text

    r = client.post(f"/ui/resumes/{new_id}/default")
    assert r.status_code == 200 and "Por defecto" in r.text

    r = client.delete(f"/ui/resumes/{new_id}")
    assert r.status_code == 200 and 'id="resume-list"' in r.text
    assert client.delete("/ui/resumes/999").status_code == 404


# ---------------------------------------------------------------------- §4.2 basics + photo


def test_basics_update(client: TestClient, cv: dict[str, Any]) -> None:
    rid = cv["resume_id"]
    r = client.put(
        f"/ui/resumes/{rid}/basics",
        data={"headline": "Backend senior", "summary": "", "_open": "1"},
    )
    assert r.status_code == 200 and r.headers["hx-trigger"] == TRIGGER
    assert 'id="sec-basics"' in r.text and "Backend senior" in r.text
    assert client.get(f"/api/resumes/{rid}/basics").json()["summary"] is None


def test_basics_422_repaints_with_spanish_message(client: TestClient, cv: dict[str, Any]) -> None:
    rid = cv["resume_id"]
    r = client.put(
        f"/ui/resumes/{rid}/basics", data={"email": "no-es-correo", "city": "Cali", "_open": "1"}
    )
    assert r.status_code == 422
    assert "hx-trigger" not in r.headers
    assert 'id="sec-basics"' in r.text  # el mismo partial
    assert "Correo electrónico inválido" in r.text
    assert 'value="no-es-correo"' in r.text and 'value="Cali"' in r.text  # lo enviado
    assert client.get(f"/api/resumes/{rid}/basics").json()["email"] == "ana@correo.co"


# ------------------------------------------------------------------------- §4.3 sections


@pytest.mark.parametrize("key", sorted(SECTION_KEYS))
def test_section_fragment(client: TestClient, cv: dict[str, Any], key: str) -> None:
    r = client.get(f"/ui/resumes/{cv['resume_id']}/sections/{key}")
    assert r.status_code == 200
    assert f'id="sec-{key}"' in r.text


def test_section_unknown_key_is_404(client: TestClient, cv: dict[str, Any]) -> None:
    assert client.get(f"/ui/resumes/{cv['resume_id']}/sections/nope").status_code == 404


@pytest.mark.parametrize("spec", SPECS, ids=[s.coll for s in SPECS])
def test_new_draft_fragment(client: TestClient, cv: dict[str, Any], spec: Any) -> None:
    parent_id = cv["resume_id"] if spec.parent == "resumes" else cv[spec.parent]
    r = client.get(f"/ui/{spec.parent}/{parent_id}/{spec.coll}/new")
    assert r.status_code == 200
    assert "is-new" in r.text and f'hx-post="/ui/{spec.parent}/{parent_id}/{spec.coll}"' in r.text
    assert "hx-put" not in r.text


CREATE_FORMS: dict[str, dict[str, str]] = {
    "links": {"kind": "github", "url": "https://github.com/ana", "label": ""},
    "experiences": {
        "role": "Dev 2",
        "company": "Globex",
        "employment_type": "full-time",
        "city": "Cali",
        "country": "co",
        "remote": "false",
        "start_date": "2018-02",
        "end_date": "2019-12",
        "is_current": "false",
        "description": "",
    },
    "achievements": {"text": "• Automaticé el despliegue", "metric_value": "40%"},
    "education": {
        "degree": "Especialización",
        "institution": "Andes",
        "level": "specialization",
        "field": "",
        "city": "",
        "start_date": "2015-01",
        "end_date": "2016-06",
        "in_progress": "false",
        "gpa": "",
        "description": "",
    },
    "skill-categories": {"name": "Cloud"},
    "skills": {"name": "Terraform", "level": "advanced", "years": "3"},
    "projects": {
        "name": "Bot",
        "role": "Autor",
        "url": "",
        "start_date": "",
        "end_date": "",
        "description": "Un bot de Telegram para recordatorios.",
    },
    "certifications": {
        "name": "CKA",
        "issuer": "CNCF",
        "issue_date": "2023-05",
        "expiry_date": "",
        "credential_id": "",
        "url": "",
    },
    "languages": {"name": "Francés", "level": "A2"},
}


@pytest.mark.parametrize("spec", SPECS, ids=[s.coll for s in SPECS])
def test_create_item_triggers_cv_changed(client: TestClient, cv: dict[str, Any], spec: Any) -> None:
    parent_id = cv["resume_id"] if spec.parent == "resumes" else cv[spec.parent]
    data = {**CREATE_FORMS[spec.coll], "_open": "1"}
    r = client.post(f"/ui/{spec.parent}/{parent_id}/{spec.coll}", data=data)
    assert r.status_code == 200, r.text
    assert r.headers["hx-trigger"] == TRIGGER
    assert f'hx-put="/ui/{spec.coll}/' in r.text  # ya es un ítem guardado


@pytest.mark.parametrize("spec", SPECS, ids=[s.coll for s in SPECS])
def test_update_item_triggers_cv_changed(client: TestClient, cv: dict[str, Any], spec: Any) -> None:
    item_id = cv[spec.coll]
    r = client.put(f"/ui/{spec.coll}/{item_id}", data={**CREATE_FORMS[spec.coll], "_open": "0"})
    assert r.status_code == 200, r.text
    assert r.headers["hx-trigger"] == TRIGGER
    assert f'data-entity-id="{item_id}"' in r.text


@pytest.mark.parametrize("spec", SPECS, ids=[s.coll for s in SPECS])
def test_delete_item_returns_empty(client: TestClient, cv: dict[str, Any], spec: Any) -> None:
    r = client.delete(f"/ui/{spec.coll}/{cv[spec.coll]}")
    assert r.status_code == 200
    assert r.text == ""
    assert r.headers["hx-trigger"] == TRIGGER
    assert client.delete(f"/ui/{spec.coll}/{cv[spec.coll]}").status_code == 404


def test_create_item_422_repaints_draft(client: TestClient, cv: dict[str, Any]) -> None:
    rid = cv["resume_id"]
    r = client.post(
        f"/ui/resumes/{rid}/experiences",
        data={
            "role": "Dev",
            "company": "",
            "start_date": "2020-01",
            "end_date": "",
            "is_current": "false",
            "remote": "false",
            "_open": "1",
        },
    )
    assert r.status_code == 422
    assert "hx-trigger" not in r.headers
    assert "is-new" in r.text and f'hx-post="/ui/resumes/{rid}/experiences"' in r.text
    assert "Campo obligatorio" in r.text  # company llegó vacío
    assert 'value="Dev"' in r.text  # conserva lo escrito


def test_update_item_422_keeps_sent_values(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.put(
        f"/ui/experiences/{cv['experiences']}",
        data={
            "role": "Dev",
            "company": "Acme",
            "start_date": "2020-01",
            "end_date": "2019-01",
            "is_current": "false",
            "remote": "false",
            "_open": "1",
        },
    )
    assert r.status_code == 422
    assert "La fecha de fin no puede ser anterior a la de inicio" in r.text
    assert 'value="2019-01"' in r.text


def test_show_in_control_sends_only_that_field(client: TestClient, cv: dict[str, Any]) -> None:
    """Contract §4.3: the ``show_in`` control does a PUT with only ``show_in`` and ``_open``."""
    r = client.put(f"/ui/experiences/{cv['experiences']}", data={"show_in": "ats", "_open": "1"})
    assert r.status_code == 200 and r.headers["hx-trigger"] == TRIGGER
    assert 'data-show-in="ats"' in r.text
    item = client.get(f"/api/resumes/{cv['resume_id']}/experiences/{cv['experiences']}").json()
    assert item["show_in"] == "ats" and item["company"] == "Acme"


def test_wrong_parent_is_404(client: TestClient, cv: dict[str, Any]) -> None:
    # Un padre de otra jerarquía (o inexistente) no sirve para la colección.
    assert client.get("/ui/experiences/9999/achievements/new").status_code == 404
    assert client.get("/ui/skill-categories/9999/skills/new").status_code == 404
    assert client.post("/ui/experiences/9999/achievements", data={"text": "x"}).status_code == 404
    assert client.get("/ui/resumes/9999/links/new").status_code == 404
    assert client.get("/resumes/9999/edit").status_code == 404
    # Un item_id de otra colección tampoco existe aquí.
    assert client.put("/ui/skills/9999", data={"name": "x"}).status_code == 404
    assert client.delete("/ui/achievements/9999").status_code == 404


# -------------------------------------------------------------------------- §4.4 preview


def test_preview_fragment_has_srcdoc_and_pages(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.get(
        f"/ui/resumes/{cv['resume_id']}/preview",
        params={"profile_id": cv["ats"], "density": "compact"},
    )
    assert r.status_code == 200
    assert "srcdoc=" in r.text and "data-preview-frame" in r.text
    assert 'id="pages-badge"' in r.text and 'hx-swap-oob="true"' in r.text
    assert "págs" in r.text or "pág." in r.text


# ----------------------------------------------------------------------- §4.5 validation


def _finding(rule_id: str, section: str | None, severity: Severity) -> FindingOut:
    return FindingOut(
        id=0,
        rule_id=rule_id,
        severity=severity,
        message=rule_id,
        section=section,
        entity=None,
        entity_id=None,
        suggestion=None,
    )


def test_sort_findings_by_section_then_severity() -> None:
    findings = [
        _finding("z", "skills", Severity.INFO),
        _finding("a", "experience", Severity.WARNING),
        _finding("b", "basics", Severity.WARNING),
        _finding("c", "basics", Severity.ERROR),
        _finding("d", "skills", Severity.ERROR),
        _finding("e", None, Severity.ERROR),
    ]
    order = [(f.section, f.severity.value) for f in sort_findings(findings)]
    assert order == [
        ("basics", "error"),
        ("basics", "warning"),
        ("experience", "warning"),
        ("skills", "error"),
        ("skills", "info"),
        (None, "error"),
    ]


def test_validation_panel(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.post(
        f"/ui/resumes/{cv['resume_id']}/validate",
        data={"profile_id": cv["ats"], "density": "wide"},
    )
    assert r.status_code == 200 and r.headers["hx-trigger"] == TRIGGER
    assert 'id="vpanel"' in r.text and "Validación" in r.text
    assert "Plataforma" in r.text
    # Los grupos salen en el orden de SECTION_ORDER (sin repetir una sección).
    groups = [chunk.split("</h3>")[0] for chunk in r.text.split('<h3 class="vpanel-group">')[1:]]
    assert len(groups) == len(set(groups))


# -------------------------------------------------------------------------- §4.6 export


def test_export_modal(client: TestClient, cv: dict[str, Any]) -> None:
    client.post(f"/ui/resumes/{cv['resume_id']}/validate", data={"profile_id": cv["ats"]})
    r = client.get(
        f"/ui/resumes/{cv['resume_id']}/export",
        params={"profile_id": cv["ats"], "density": "normal"},
    )
    assert r.status_code == 200
    assert 'id="export-modal"' in r.text and 'name="formats"' in r.text
    assert "Última validación" in r.text  # el último reporte del perfil activo


def test_export_result(client: TestClient, cv: dict[str, Any]) -> None:
    r = client.post(
        f"/ui/resumes/{cv['resume_id']}/export",
        **urlencoded(
            [
                ("profile_id", str(cv["ats"])),
                ("formats", "json"),
                ("formats", "pdf"),
                ("with_photo_variant", "false"),
            ]
        ),
    )
    assert r.status_code == 200, r.text
    assert r.headers["hx-trigger"] == TRIGGER
    assert "result-banner" in r.text


# ------------------------------------------------------------------------- §4.7 profiles


def test_profile_crud(client: TestClient, cv: dict[str, Any]) -> None:
    rid = cv["resume_id"]
    r = client.post(f"/ui/resumes/{rid}/profiles", data={"name": "Correo 2", "destination": "mail"})
    assert r.status_code == 200 and r.text == ""
    assert r.headers["hx-redirect"].startswith(f"/resumes/{rid}/profiles?profile_id=")
    new_id = int(r.headers["hx-redirect"].rsplit("=", 1)[1])
    assert client.get(f"/api/resumes/{rid}/profiles/{new_id}").json()["theme"] == "slate"

    again = client.post(
        f"/ui/resumes/{rid}/profiles", data={"name": "Correo 2", "destination": "mail"}
    )
    assert again.status_code == 409

    r = client.put(
        f"/ui/profiles/{new_id}",
        # ``include_photo`` llega dos veces (hidden + checkbox marcado): gana la última.
        **urlencoded(
            [
                ("name", "Correo 2"),
                ("density", "compact"),
                ("date_format", "MMM YYYY"),
                ("max_pages", "1"),
                ("theme", "ocean"),
                ("accent_color", ""),
                ("include_photo", "false"),
                ("include_photo", "true"),
            ]
        ),
    )
    assert r.status_code == 200 and r.headers["hx-trigger"] == TRIGGER
    assert 'id="profile-settings"' in r.text
    saved = client.get(f"/api/resumes/{rid}/profiles/{new_id}").json()
    assert saved["theme"] == "ocean" and saved["accent_color"] is None
    assert saved["max_pages"] == 1 and saved["include_photo"] is True

    # 422: re-pinta el mismo partial con el mensaje en español (el macro ``field`` lo muestra).
    r = client.put(f"/ui/profiles/{new_id}", data={"name": "", "density": "normal"})
    assert r.status_code == 422 and 'id="profile-settings"' in r.text
    assert "hx-trigger" not in r.headers
    assert "Campo obligatorio" in r.text
    # Un color inválido también devuelve 422 (profile_settings.html no tiene hueco de error
    # para ``accent_color``: reportado a Diseño).
    assert client.put(f"/ui/profiles/{new_id}", data={"accent_color": "rojo"}).status_code == 422

    r = client.delete(f"/ui/profiles/{new_id}")
    assert r.status_code == 200 and r.headers["hx-redirect"] == f"/resumes/{rid}/profiles"


def test_cannot_delete_last_profile(client: TestClient, cv: dict[str, Any]) -> None:
    client.delete(f"/ui/profiles/{cv['mail']}")
    r = client.delete(f"/ui/profiles/{cv['ats']}")
    assert r.status_code == 409 and "único perfil" in r.text
