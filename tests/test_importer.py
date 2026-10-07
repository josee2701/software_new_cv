"""Importer (spec §11, §17.4): app round-trip, LinkedIn-style, dirty PDF, DOCX, apply, API, CLI."""

from __future__ import annotations

import io
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner
from weasyprint import HTML

from app.seed import run_seed
from export.docx import to_docx_bytes
from export.pdf import html_to_pdf
from importer import ImportFormatError, detect_format, parse_document
from importer.dates import find_range, parse_side
from importer.parsers import language_level, parse_location, split_title
from importer.text import fix_case, split_list
from models.enums import Destination, LanguageLevel, LinkKind
from render.filters import url_display
from render.renderer import render
from schemas import ResumeCreate, ResumeOut
from schemas.importer import ImportedExperience, ImportPreview, ScoredDate, ScoredStr
from services import InvalidDataError, NotFoundError, ResumeService
from services.importer import ImportService

FIXTURES = Path(__file__).parent / "fixtures" / "import"
MIN_CONFIDENCE = 0.8


# ------------------------------------------------------------------------ fixtures


@pytest.fixture
def seeded(session: Session) -> ResumeOut:
    return ResumeService(session).get_out(run_seed(session).resume_id)


def _ats(cv: ResumeOut) -> Any:
    return next(p for p in cv.profiles if p.destination is Destination.ATS)


def app_pdf(cv: ResumeOut) -> bytes:
    """PDF exported by this app (Plataforma profile) — fixture (1)."""
    return html_to_pdf(render(cv, _ats(cv)).html, title="CV", author="cv-ats").data


def fixture_pdf(name: str) -> bytes:
    data: bytes = HTML(filename=str(FIXTURES / name)).write_pdf()
    return data


# ------------------------------------------------------------------------ §17.4 measurement


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


def _url(value: str | None) -> str | None:
    return url_display(value).lower() if value else None


def compare(original: ResumeOut, preview: ImportPreview) -> tuple[int, int, list[str]]:
    """(recovered, total, misses): a field counts when the original has a value and the
    preview has the same (normalized) value with confidence ≥ 0.8. Only fields that the ats
    template renders are compared (employment type, skill levels, etc. are not in the PDF)."""
    checks: list[tuple[str, Any, Any, float]] = []
    b, pb = original.basics, preview.basics
    for name in ("full_name", "headline", "email", "phone", "city", "region", "country", "summary"):
        scored = getattr(pb, name)
        checks.append((f"basics.{name}", getattr(b, name), scored.value, scored.confidence))
    links = {link.kind: link for link in preview.links}
    for link in original.links:
        got = links.get(link.kind)
        checks.append((f"links.{link.kind.value}", _url(link.url), _url(got.url) if got else None,
                       got.confidence if got else 0))  # fmt: skip
    for i, exp in enumerate(original.experiences):
        got_exp = preview.experiences[i] if i < len(preview.experiences) else ImportedExperience()
        for name in ("role", "company", "city", "country", "start_date", "description"):
            scored = getattr(got_exp, name)
            checks.append((f"exp{i}.{name}", getattr(exp, name), scored.value, scored.confidence))
        if exp.is_current:
            checks.append((f"exp{i}.is_current", True, got_exp.is_current.value,
                           got_exp.is_current.confidence))  # fmt: skip
        else:
            checks.append((f"exp{i}.end_date", exp.end_date, got_exp.end_date.value,
                           got_exp.end_date.confidence))  # fmt: skip
        if exp.remote:
            checks.append((f"exp{i}.remote", True, got_exp.remote.value, got_exp.remote.confidence))
        for j, ach in enumerate(exp.achievements):
            got = got_exp.achievements[j] if j < len(got_exp.achievements) else None
            checks.append((f"exp{i}.ach{j}", ach.text, got.text if got else None,
                           got.confidence if got else 0))  # fmt: skip
        checks.append((f"exp{i}.technologies", exp.technologies, got_exp.technologies.value,
                       got_exp.technologies.confidence))  # fmt: skip
    for i, edu in enumerate(original.education):
        got_edu = preview.education[i] if i < len(preview.education) else None
        for name in ("degree", "institution", "city", "start_date", "end_date", "gpa"):
            scored = getattr(got_edu, name) if got_edu else ScoredStr()
            checks.append((f"edu{i}.{name}", getattr(edu, name), scored.value, scored.confidence))
    for i, cat in enumerate(original.skill_categories):
        got_cat = preview.skill_categories[i] if i < len(preview.skill_categories) else None
        names = [s.text for s in got_cat.skills] if got_cat else []
        conf = min((s.confidence for s in got_cat.skills), default=0) if got_cat else 0
        checks.append((f"skills{i}.name", cat.name, got_cat.name.value if got_cat else None,
                       got_cat.name.confidence if got_cat else 0))  # fmt: skip
        checks.append((f"skills{i}.skills", [s.name for s in cat.skills], names, conf))
    for i, proj in enumerate(original.projects):
        got_proj = preview.projects[i] if i < len(preview.projects) else None
        for name in ("name", "role", "description", "start_date", "end_date", "technologies"):
            scored = getattr(got_proj, name) if got_proj else ScoredDate()
            checks.append((f"proj{i}.{name}", getattr(proj, name), scored.value, scored.confidence))
        url_scored = got_proj.url if got_proj else ScoredStr()
        checks.append((f"proj{i}.url", _url(proj.url), _url(url_scored.value),
                       url_scored.confidence))  # fmt: skip
    for i, cert in enumerate(original.certifications):
        got_cert = preview.certifications[i] if i < len(preview.certifications) else None
        for name in ("name", "issuer", "issue_date", "expiry_date", "credential_id"):
            scored = getattr(got_cert, name) if got_cert else ScoredStr()
            checks.append((f"cert{i}.{name}", getattr(cert, name), scored.value, scored.confidence))
        url_scored = got_cert.url if got_cert else ScoredStr()
        checks.append((f"cert{i}.url", _url(cert.url), _url(url_scored.value),
                       url_scored.confidence))  # fmt: skip
    for i, lang in enumerate(original.languages):
        got_lang = preview.languages[i] if i < len(preview.languages) else None
        checks.append((f"lang{i}.name", lang.name, got_lang.name.value if got_lang else None,
                       got_lang.name.confidence if got_lang else 0))  # fmt: skip
        checks.append((f"lang{i}.level", lang.level, got_lang.level.value if got_lang else None,
                       got_lang.level.confidence if got_lang else 0))  # fmt: skip

    relevant = [c for c in checks if c[1] not in (None, "", [], False)]
    misses = [
        f"{path}: {orig!r} → {got!r} ({conf})"
        for path, orig, got, conf in relevant
        if _norm(orig) != _norm(got) or conf < MIN_CONFIDENCE
    ]
    return len(relevant) - len(misses), len(relevant), misses


def test_roundtrip_app_pdf_recovers_90_percent(seeded: ResumeOut) -> None:
    preview = parse_document(app_pdf(seeded), "Andres_Rojas_CV_ats.pdf")
    recovered, total, misses = compare(seeded, preview)
    ratio = recovered / total
    print(f"\n§17.4 PDF ats: {recovered}/{total} = {ratio:.1%} ; fallos: {misses}")
    assert total >= 80
    assert ratio >= 0.90, misses
    assert preview.source == "pdf" and preview.warnings == []


def test_roundtrip_app_docx(seeded: ResumeOut) -> None:
    preview = parse_document(to_docx_bytes(seeded, _ats(seeded)), "cv.docx")
    recovered, total, misses = compare(seeded, preview)
    print(f"\n§17.4 DOCX: {recovered}/{total} = {recovered / total:.1%} ; fallos: {misses}")
    assert preview.source == "docx"
    assert recovered / total >= 0.90, misses


# ------------------------------------------------------------------------ LinkedIn / dirty


def test_linkedin_style_two_columns() -> None:
    preview = parse_document(fixture_pdf("linkedin.html"), "Profile.pdf")
    b = preview.basics
    assert b.full_name.value == "Andrés Felipe Rojas Martínez"
    assert b.headline.value.startswith("Ingeniero Backend Senior")
    assert (b.email.value, b.phone.value) == ("andres.rojas@example.com", "+573001234567")
    assert (b.city.value, b.country.value) == ("Bogotá", "CO")
    assert "8 años" in (b.summary.value or "")
    assert [link.kind for link in preview.links] == [LinkKind.LINKEDIN]
    exps = preview.experiences
    assert [e.company.value for e in exps] == [
        "Banco Andino Digital", "Mercado Ágil S.A.S.", "Soluciones TIC Ltda.",
    ]  # fmt: skip
    assert [e.role.value for e in exps] == [
        "Ingeniero Backend Senior", "Desarrollador Backend", "Desarrollador de Software",
    ]  # fmt: skip
    assert exps[0].is_current.value and exps[0].start_date.value == date(2022, 3, 1)
    assert exps[1].end_date.value == date(2022, 2, 1)
    assert exps[2].city.value == "Medellín"
    assert [e.institution.value for e in preview.education] == [
        "Universidad de los Andes", "Universidad Nacional de Colombia",
    ]  # fmt: skip
    assert preview.education[1].start_date.value == date(2011, 1, 1)
    assert preview.skill_categories[0].skills[0].text == "Python"
    assert [(lang.name.value, lang.level.value) for lang in preview.languages] == [
        ("Español", LanguageLevel.NATIVE), ("Inglés", LanguageLevel.C1),
    ]  # fmt: skip
    certs = preview.certifications
    assert [c.name.value for c in certs] == [
        "AWS Certified Solutions Architect – Associate",
        "Certified Kubernetes Application Developer",
    ]
    assert all(c.issuer.value == "" and c.issuer.confidence < 0.6 for c in certs)
    assert not any("Page 1" in line for line in preview.unassigned)


def test_dirty_pdf() -> None:
    preview = parse_document(fixture_pdf("dirty.html"), "hv.pdf")
    b = preview.basics
    assert b.full_name.value == "Juan Camilo Pérez Gómez"
    assert b.full_name.confidence < MIN_CONFIDENCE  # re-cased → flagged for review
    assert (b.phone.value, b.city.value, b.country.value) == ("+573001234567", "Cali", "CO")
    assert b.email.value == "juan.perez@correo.com"
    assert [s.kind for s in preview.sections][1:] == [
        "summary", "experience", "education", "skills", "languages",
    ]  # fmt: skip
    first, second = preview.experiences
    assert (first.role.value, first.company.value) == (
        "Desarrollador Backend", "Fintech Pacífico S.A.S.",
    )  # fmt: skip
    assert first.is_current.value and first.start_date.value == date(2019, 1, 1)
    assert [a.text[:12] for a in first.achievements] == [
        "Implementé p",
        "Reduje los t",
        "Automaticé d",
    ]
    assert (second.role.value, second.company.value) == (
        "Analista de Sistemas", "Comercializadora del Valle",
    )  # fmt: skip
    assert (second.start_date.value, second.end_date.value) == (date(2016, 1, 1), date(2018, 12, 1))
    assert second.achievements[0].text.endswith("para 200 usuarios.")  # continuation joined
    edu = preview.education[0]
    assert (edu.degree.value, edu.institution.value) == (
        "Ingeniería de Sistemas",
        "Universidad del Valle",
    )
    assert [s.text for s in preview.skill_categories[0].skills] == [
        "Python", "Django", "PostgreSQL", "Docker", "Git", "Linux",
    ]  # fmt: skip
    assert [(x.name.value, x.level.value) for x in preview.languages] == [
        ("Inglés", LanguageLevel.B2), ("Francés", LanguageLevel.A2),
    ]  # fmt: skip


def test_scanned_pdf_and_bad_format() -> None:
    image = Image.new("RGB", (800, 1000), "white")
    ImageDraw.Draw(image).text((50, 50), "Juan Perez", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PDF")
    preview = parse_document(buffer.getvalue(), "scan.pdf")
    assert preview.experiences == [] and "no tiene texto" in preview.warnings[0]
    with pytest.raises(ImportFormatError):
        detect_format(b"hola", "cv.txt")
    assert detect_format(b"PK\x03\x04...", "cv.docx") == "docx"


# ------------------------------------------------------------------------ units


def test_parsing_helpers() -> None:
    assert parse_side("03/2021") == (date(2021, 3, 1), 0.95)
    assert parse_side("marzo de 2021") == (date(2021, 3, 1), 0.9)
    assert parse_side("Sep 2020") == (date(2020, 9, 1), 0.9)
    assert parse_side("2019") == (date(2019, 1, 1), 0.7)
    assert parse_side("13/2020") is None
    dr = find_range("enero de 2020 - marzo de 2022 (2 años 3 meses)")
    assert dr is not None and (dr.start, dr.end, dr.current) == (
        date(2020, 1, 1),
        date(2022, 3, 1),
        False,
    )
    current = find_range("2019 - Actualidad")
    assert current is not None and current.current and current.end is None
    assert find_range("Mar 2021 – Present") is not None
    assert find_range("2022 - 2019") is None  # end before start
    assert split_title("Cargo — Empresa") == ("Cargo", "Empresa", 0.92)
    assert split_title("Ingeniero en Sistemas en ACME")[:2] == ("Ingeniero en Sistemas", "ACME")
    assert split_title("Solo cargo")[1] == ""
    assert parse_location("Bogotá, Cundinamarca, Colombia · Remoto") == (
        "Bogotá", "Cundinamarca", "CO", True,
    )  # fmt: skip
    assert parse_location("Remote") == (None, None, None, True)
    assert parse_location("España") == (None, None, "ES", False)
    assert language_level("C1 — Avanzado") == (LanguageLevel.C1, 0.95)
    assert language_level("Native or Bilingual")[0] is LanguageLevel.NATIVE
    assert language_level("???") == (None, 0.0)
    assert fix_case("Mercado Ágil S.A.S.") == ("Mercado Ágil S.A.S.", False)
    assert fix_case("DESARROLLADOR BACKEND")[0] == "Desarrollador Backend"
    assert split_list("Python, CI/CD | Git · Linux / Docker") == [
        "Python", "CI/CD", "Git", "Linux", "Docker",
    ]  # fmt: skip


# ------------------------------------------------------------------------ apply (service)


def test_apply_replace_into_empty_resume(session: Session, seeded: ResumeOut) -> None:
    preview = parse_document(app_pdf(seeded), "cv.pdf")
    target = ResumeService(session).create(ResumeCreate(name="Importado"))
    result = ImportService(session).apply(target.id, preview, "replace")
    assert result.skipped == []
    assert result.created == {
        "links": 2, "experiences": 3, "education": 2, "skill_categories": 3, "skills": 14,
        "projects": 2, "certifications": 2, "languages": 2,
    }  # fmt: skip
    imported = result.resume
    assert imported.basics.full_name == seeded.basics.full_name
    assert imported.basics.phone == seeded.basics.phone
    assert [e.company for e in imported.experiences] == [e.company for e in seeded.experiences]
    assert (
        imported.experiences[0].achievements[0].text == seeded.experiences[0].achievements[0].text
    )
    assert imported.experiences[0].technologies == seeded.experiences[0].technologies
    assert imported.certifications[0].credential_id == "AWS-SAA-8F3K2L"
    # the preview re-parsed from the imported resume is still ≥ 90%
    again = parse_document(app_pdf(imported), "cv.pdf")
    recovered, total, _ = compare(imported, again)
    assert recovered / total >= 0.90


def test_apply_append_merges_and_skips(session: Session, seeded: ResumeOut) -> None:
    preview = parse_document(app_pdf(seeded), "cv.pdf")
    service = ImportService(session)
    result = service.apply(seeded.id, preview, "append")
    out = result.resume
    assert len(out.experiences) == 6
    assert len(out.skill_categories) == 3  # merged by name, no duplicated skills
    assert sum(len(c.skills) for c in out.skill_categories) == 14
    assert len(out.languages) == 2 and len(out.links) == 2
    reasons = {s.path: s.reason for s in result.skipped}
    assert reasons["languages.Español"] == "Ya existe"
    assert "links.linkedin" in reasons


def test_apply_reports_invalid_items(session: Session) -> None:
    target = ResumeService(session).create(ResumeCreate(name="X"))
    preview = ImportPreview(source="pdf")
    preview.basics.email = ScoredStr(value="no-es-correo", confidence=0.9)
    preview.basics.full_name = ScoredStr(value="Ana Ruiz", confidence=0.9)
    preview.experiences = [
        ImportedExperience(role=ScoredStr(value="Dev"), company=ScoredStr(value="ACME")),
        ImportedExperience(
            role=ScoredStr(value="Dev"), company=ScoredStr(value=""),
            start_date=ScoredDate(value=date(2020, 1, 1)),
            end_date=ScoredDate(value=date(2021, 1, 1)),
        ),
    ]  # fmt: skip
    result = ImportService(session).apply(target.id, preview)
    paths = {s.path for s in result.skipped}
    assert {"basics.email", "experiences.0", "experiences.1"} <= paths
    assert result.resume.basics.full_name == "Ana Ruiz"
    assert result.resume.experiences == []


def test_preview_service_errors(session: Session) -> None:
    service = ImportService(session)
    with pytest.raises(NotFoundError):
        service.preview(999, b"%PDF-1.4")
    target = ResumeService(session).create(ResumeCreate(name="X"))
    with pytest.raises(InvalidDataError):
        service.preview(target.id, b"")
    with pytest.raises(InvalidDataError):
        service.preview(target.id, b"texto plano", "cv.txt")


# ------------------------------------------------------------------------ API + CLI


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    from app.db import get_session
    from app.main import create_app

    app = create_app()

    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


def test_import_api_preview_and_apply(client: TestClient, session: Session) -> None:
    source = ResumeService(session).get_out(run_seed(session).resume_id)
    rid = client.post("/api/resumes", json={"name": "Destino"}).json()["id"]
    files = {"file": ("Andres_Rojas_CV_ats.pdf", app_pdf(source), "application/pdf")}
    r = client.post(f"/api/resumes/{rid}/import", files=files)
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["basics"]["email"] == {"value": "andres.rojas@example.com", "confidence": 0.95}
    assert client.get(f"/api/resumes/{rid}").json()["experiences"] == []  # preview never writes
    preview["experiences"][0]["role"]["value"] = "Líder Backend"  # user edit
    r = client.post(
        f"/api/resumes/{rid}/import/apply", json={"preview": preview, "mode": "replace"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["resume"]["experiences"][0]["role"] == "Líder Backend"
    bad = client.post(
        f"/api/resumes/{rid}/import", files={"file": ("x.txt", b"hola", "text/plain")}
    )
    assert bad.status_code == 422
    assert client.post("/api/resumes/999/import", files=files).status_code == 404


def test_cli_import(tmp_path: Path, _isolated_data_dir: Path, seeded: ResumeOut) -> None:
    from app.cli import app
    from app.db import get_engine, get_sessionmaker

    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(app_pdf(seeded))
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    runner = CliRunner()
    try:
        assert runner.invoke(app, ["seed"]).exit_code == 0
        preview = runner.invoke(app, ["import", str(pdf), "--resume", "1"])
        assert preview.exit_code == 0, preview.output
        assert "3 experiencias" in preview.output and "Vista previa" in preview.output
        applied = runner.invoke(app, ["import", str(pdf), "--resume", "1", "--apply"])
        assert applied.exit_code == 0, applied.output
        assert "experiences=3" in applied.output
        missing = runner.invoke(app, ["import", str(tmp_path / "nope.pdf"), "--resume", "1"])
        assert missing.exit_code != 0
    finally:
        get_engine().dispose()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()
