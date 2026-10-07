"""API CRUD flow (spec §6, §14)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.main import create_app


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


def test_full_crud_flow(client: TestClient) -> None:
    r = client.post("/api/resumes", json={"name": "General", "is_default": True})
    assert r.status_code == 201, r.text
    resume = r.json()
    rid = resume["id"]
    assert [p["name"] for p in resume["profiles"]] == ["Plataforma", "Correo"]
    assert len(resume["profiles"][0]["sections"]) == 7

    assert client.get("/api/resumes").json()[0]["id"] == rid
    assert client.patch(f"/api/resumes/{rid}", json={"notes": "nota"}).json()["notes"] == "nota"

    r = client.put(
        f"/api/resumes/{rid}/basics",
        json={
            "full_name": "Ana Gómez",
            "headline": "Backend",
            "email": "ana@correo.co",
            "phone": "300 123 4567",
            "city": "Bogotá",
            "country": "co",
            "summary": "Ingeniera backend.",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "+573001234567"
    assert client.get(f"/api/resumes/{rid}/basics").json()["country"] == "CO"

    # links
    li = client.post(
        f"/api/resumes/{rid}/links", json={"kind": "linkedin", "url": "linkedin.com/in/ana"}
    ).json()
    gh = client.post(
        f"/api/resumes/{rid}/links", json={"kind": "github", "url": "https://github.com/ana"}
    ).json()
    r = client.put(f"/api/resumes/{rid}/links/order", json=[gh["id"], li["id"]])
    assert [x["id"] for x in r.json()] == [gh["id"], li["id"]]
    r = client.post(f"/api/resumes/{rid}/links", json={"kind": "github", "url": "https://x.io"})
    assert r.status_code == 409

    # experiences + achievements + technologies
    r = client.post(
        f"/api/resumes/{rid}/experiences",
        json={"company": "ACME", "role": "Dev", "start_date": "2021-03", "is_current": True},
    )
    assert r.status_code == 201, r.text
    exp = r.json()
    assert exp["start_date"] == "2021-03-01"
    old = client.post(
        f"/api/resumes/{rid}/experiences",
        json={"company": "Old", "role": "Dev", "start_date": "2018-01", "end_date": "2020-12"},
    ).json()
    ids = [x["id"] for x in client.get(f"/api/resumes/{rid}/experiences").json()]
    assert ids == [exp["id"], old["id"]]
    r = client.patch(f"/api/resumes/{rid}/experiences/{old['id']}", json={"role": "Senior"})
    assert r.json()["role"] == "Senior"

    a = client.post(
        f"/api/experiences/{exp['id']}/achievements",
        json={"text": "• Reduje costos 20%", "metric_value": "20%"},
    ).json()
    assert a["text"] == "Reduje costos 20%"
    r = client.put(f"/api/experiences/{exp['id']}/technologies", json=["python", "Docker"])
    assert r.json() == ["python", "Docker"]

    # other sections
    assert (
        client.post(
            f"/api/resumes/{rid}/education", json={"institution": "UN", "degree": "Ing"}
        ).status_code
        == 201
    )
    cat = client.post(f"/api/resumes/{rid}/skill-categories", json={"name": "Lenguajes"}).json()
    r = client.post(f"/api/skill-categories/{cat['id']}/skills", json={"name": "Python"})
    assert r.status_code == 201, r.text
    proj = client.post(
        f"/api/resumes/{rid}/projects", json={"name": "cv-ats", "description": "Editor"}
    ).json()
    assert client.put(f"/api/projects/{proj['id']}/technologies", json=["FastAPI"]).json() == [
        "FastAPI"
    ]
    assert (
        client.post(
            f"/api/resumes/{rid}/certifications", json={"name": "AWS", "issuer": "Amazon"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/resumes/{rid}/languages", json={"name": "Inglés", "level": "B2"}
        ).status_code
        == 201
    )

    # technologies autocomplete
    names = [t["canonical"] for t in client.get("/api/technologies", params={"q": "py"}).json()]
    assert names == ["python"]

    # profiles
    profiles = client.get(f"/api/resumes/{rid}/profiles").json()
    mail = next(p for p in profiles if p["destination"] == "mail")
    r = client.patch(f"/api/resumes/{rid}/profiles/{mail['id']}", json={"destination": "ats"})
    assert r.json()["theme"] is None
    sections = [
        {"section": s, "visible": s != "projects"}
        for s in [
            "experience",
            "summary",
            "education",
            "skills",
            "projects",
            "certifications",
            "languages",
        ]
    ]
    r = client.put(f"/api/profiles/{mail['id']}/sections", json=sections)
    assert r.status_code == 200, r.text
    assert r.json()["sections"][0]["section"] == "experience"
    r = client.post(
        f"/api/resumes/{rid}/profiles",
        json={"name": "Banca", "destination": "mail", "theme": "ocean"},
    )
    assert r.status_code == 201

    # full tree
    tree = client.get(f"/api/resumes/{rid}").json()
    assert tree["experiences"][0]["technologies"] == ["python", "Docker"]
    assert tree["experiences"][0]["achievements"][0]["metric_value"] == "20%"

    # duplicate, snapshot, delete
    dup = client.post(f"/api/resumes/{rid}/duplicate", json={"name": "Copia"})
    assert dup.status_code == 201 and dup.json()["name"] == "Copia"
    snap = client.post(f"/api/resumes/{rid}/snapshots", json={"label": "v1"})
    assert snap.status_code == 201
    assert client.get(f"/api/snapshots/{snap.json()['id']}").json()["payload"]["id"] == rid
    assert client.delete(f"/api/resumes/{rid}/experiences/{old['id']}").status_code == 204
    assert client.delete(f"/api/resumes/{rid}").status_code == 204
    assert client.get(f"/api/resumes/{rid}").status_code == 404


def test_validation_error_shape(client: TestClient) -> None:
    rid = client.post("/api/resumes", json={"name": "X"}).json()["id"]
    r = client.post(
        f"/api/resumes/{rid}/experiences",
        json={"company": "", "role": "Dev", "start_date": "2021-13"},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert {"field": "company", "msg": "Campo obligatorio"} in detail
    assert all(set(d) == {"field", "msg"} for d in detail)

    r = client.post(
        f"/api/resumes/{rid}/experiences",
        json={"company": "A", "role": "Dev", "start_date": "2021-03", "end_date": "2020-01"},
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["field"] == "end_date"

    r = client.put(f"/api/resumes/{rid}/basics", json={"email": "nope"})
    assert r.json()["detail"] == [{"field": "email", "msg": "Correo electrónico inválido"}]

    r = client.post(
        f"/api/resumes/{rid}/profiles",
        json={"name": "P", "destination": "ats", "include_photo": True},
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["field"] == "include_photo"


def test_domain_errors(client: TestClient) -> None:
    assert client.post("/api/resumes", json={"name": "A"}).status_code == 201
    r = client.post("/api/resumes", json={"name": "A"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Ya existe un CV con ese nombre"
    assert client.get("/api/resumes/999").status_code == 404
    r = client.put("/api/resumes/1/experiences/order", json=[42])
    assert r.status_code == 422


def test_preview_endpoint(client: TestClient) -> None:
    from render.renderer import TEMPLATES_DIR

    rid = client.post("/api/resumes", json={"name": "P"}).json()["id"]
    client.put(f"/api/resumes/{rid}/basics", json={"full_name": "Ana Gómez"})
    profiles = client.get(f"/api/resumes/{rid}/profiles").json()
    r = client.get(
        f"/api/resumes/{rid}/preview",
        params={"profile_id": profiles[0]["id"], "density": "compact"},
    )
    if not (TEMPLATES_DIR / "ats" / "base.html").is_file():
        assert r.status_code == 503
        return
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Ana Gómez" in r.text
    assert "density-compact" in r.text
    assert int(r.headers["X-Pages"]) >= 1
    assert client.get(f"/api/resumes/{rid}/preview", params={"profile_id": 999}).status_code == 404


def test_export_and_download_flow(client: TestClient) -> None:
    from app.routers.exports import get_validation_engine
    from services.export import null_engine

    client.app.dependency_overrides[get_validation_engine] = lambda: null_engine  # type: ignore[attr-defined]
    rid = client.post("/api/resumes", json={"name": "Export"}).json()["id"]
    client.put(f"/api/resumes/{rid}/basics", json={
        "full_name": "Ana María Gómez Ruiz", "headline": "Backend", "email": "ana@correo.co",
        "phone": "3001234567", "city": "Bogotá", "summary": "Ingeniera backend.",
    })  # fmt: skip
    exp = client.post(f"/api/resumes/{rid}/experiences", json={
        "company": "ACME", "role": "Dev", "start_date": "2021-03", "is_current": True,
    }).json()  # fmt: skip
    client.post(
        f"/api/experiences/{exp['id']}/achievements",
        json={"text": "Reduje costos de nube 20% en 6 meses"},
    )
    profiles = client.get(f"/api/resumes/{rid}/profiles").json()
    ats = next(p for p in profiles if p["destination"] == "ats")

    r = client.post(
        f"/api/resumes/{rid}/export",
        json={"profile_id": ats["id"], "formats": ["pdf", "docx", "json"]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    job = body["job"]
    assert job["status"] == "done" and body["score"] == 100
    assert body["files"] == [
        "Ana_Gomez_CV_ats.pdf",
        "Ana_Gomez_CV_ats.docx",
        "Ana_Gomez_CV_ats.json",
    ]
    assert body["coverage"] >= 0.95
    assert client.get(f"/api/exports/{job['id']}").json()["status"] == "done"

    pdf = client.get(body["downloads"][0])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "Ana_Gomez_CV_ats.pdf" in pdf.headers["content-disposition"]
    js = client.get(f"/api/exports/{job['id']}/download", params={"format": "json"})
    assert js.json()["id"] == rid
    assert (
        client.get(
            f"/api/exports/{job['id']}/download", params={"format": "pdf", "variant": "sinfoto"}
        ).status_code
        == 404
    )
    assert client.get("/api/exports/999/download").status_code == 404
    r = client.post(f"/api/resumes/{rid}/export", json={"profile_id": ats["id"], "formats": []})
    assert r.status_code == 422


def test_export_blocked_with_fake_engine(client: TestClient) -> None:
    from app.routers.exports import get_validation_engine
    from models.enums import Severity
    from validator.types import Finding, Report

    def blocking(ctx: object) -> Report:
        return Report(score=50, findings=(Finding("contact.email_present", Severity.ERROR, "x"),))

    client.app.dependency_overrides[get_validation_engine] = lambda: blocking  # type: ignore[attr-defined]
    rid = client.post("/api/resumes", json={"name": "Bloq"}).json()["id"]
    ats = client.get(f"/api/resumes/{rid}/profiles").json()[0]
    body = client.post(f"/api/resumes/{rid}/export", json={"profile_id": ats["id"]}).json()
    assert body["job"]["status"] == "blocked"
    assert body["files"] == [] and body["errors"] == 1
    assert body["findings"][0]["rule_id"] == "contact.email_present"


_HAS_ENGINE = __import__("importlib").util.find_spec("validator.engine") is not None


@pytest.mark.xfail(
    not _HAS_ENGINE, reason="validator.engine (Backend-Validador) aún no existe", strict=True
)
def test_export_ats_blocked_by_real_validator(client: TestClient) -> None:
    rid = client.post("/api/resumes", json={"name": "Vacío"}).json()["id"]
    ats = client.get(f"/api/resumes/{rid}/profiles").json()[0]
    body = client.post(f"/api/resumes/{rid}/export", json={"profile_id": ats["id"]}).json()
    assert body["job"]["status"] == "blocked"


def test_snapshot_restore_api(client: TestClient) -> None:
    rid = client.post("/api/resumes", json={"name": "Snap"}).json()["id"]
    client.put(f"/api/resumes/{rid}/basics", json={"full_name": "Antes"})
    snap = client.post(f"/api/resumes/{rid}/snapshots", json={"label": "v1"}).json()
    client.put(f"/api/resumes/{rid}/basics", json={"full_name": "Después"})
    r = client.post(f"/api/snapshots/{snap['id']}/restore")
    assert r.status_code == 200, r.text
    assert r.json()["basics"]["full_name"] == "Antes"
    assert client.post("/api/snapshots/999/restore").status_code == 404
