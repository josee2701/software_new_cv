"""Validation persistence, API and CLI; example resume (seed) integration (spec §6, §13, §17)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jinja2 import TemplateNotFound
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import app.db
import services.validation as validation_module
from app.cli import app as cli_app
from app.db import get_session
from app.main import create_app
from app.seed import run_seed
from models import ValidationFinding, ValidationReport
from models.enums import Destination, Severity
from schemas import ResumeCreate
from services import ProfileService, ResumeService
from services.errors import ConflictError, NotFoundError
from services.validation import (
    ValidationService,
    count_pages,
    render_for_validation,
    run_and_save,
    save_report,
)
from validator.docs import rules_markdown
from validator.types import Finding, Report


@pytest.fixture
def seeded(session: Session) -> int:
    return run_seed(session).resume_id


def _profile_id(session: Session, rid: int, destination: Destination) -> int:
    cv = ResumeService(session).get_out(rid)
    return next(p.id for p in cv.profiles if p.destination is destination)


# ------------------------------------------------------------------ seed integration


def test_seed_resume_platform_passes(session: Session, seeded: int) -> None:
    """Spec §17: example resume with the Plataforma profile → score ≥ 90 and no errors."""
    pid = _profile_id(session, seeded, Destination.ATS)
    report = ValidationService(session).run_and_save(seeded, pid, render_html=True)
    assert report.score >= 90, [f.message for f in report.findings]
    assert report.errors == 0, [f.message for f in report.findings]
    rule_ids = {f.rule_id for f in report.findings}
    assert "length.pages" not in rule_ids  # the real HTML fits in max_pages
    assert report.profile_id == pid and report.resume_id == seeded


def test_seed_resume_mail_passes(session: Session, seeded: int) -> None:
    pid = _profile_id(session, seeded, Destination.MAIL)
    report = run_and_save(session, seeded, pid, render_html=True)
    assert report.score >= 90 and report.errors == 0
    assert "photo.present_mail" in {f.rule_id for f in report.findings}


def test_empty_resume_has_blocking_errors(session: Session) -> None:
    rid = ResumeService(session).create(ResumeCreate(name="Vacío")).id
    profile, report = ValidationService(session).run(rid)
    assert profile.destination is Destination.ATS
    assert report.blocks_export(Destination.ATS)
    ids = {f.rule_id for f in report.findings}
    assert {"contact.email_present", "structure.required_sections"} <= ids


# ------------------------------------------------------------------ persistence


def test_run_and_save_persists_report_and_findings(session: Session, seeded: int) -> None:
    report = ValidationService(session).run_and_save(seeded, html="<table></table>")
    row = session.get(ValidationReport, report.id)
    assert row is not None
    assert (row.score, row.errors, row.warnings) == (report.score, report.errors, report.warnings)
    assert [f.rule_id for f in row.findings] == [f.rule_id for f in report.findings]
    assert "structure.no_tables" in {f.rule_id for f in report.findings}
    assert ValidationService(session).get_report(report.id) == report


def test_save_report_truncates_and_clamps(session: Session, seeded: int) -> None:
    finding = Finding(
        rule_id="x" * 70,
        severity=Severity.WARNING,
        message="m" * 400,
        section="s" * 30,
        entity="e" * 40,
        entity_id=3,
        suggestion="s" * 301,
    )
    out = save_report(
        session, resume_id=seeded, profile_id=None, report=Report(score=120, findings=(finding,))
    )
    (saved,) = out.findings
    assert out.score == 100 and out.profile_id is None and out.warnings == 1
    assert len(saved.message) == 300 and saved.message.endswith("…")
    assert (len(saved.rule_id), len(saved.section or ""), len(saved.entity or "")) == (60, 20, 30)
    assert len(saved.suggestion or "") == 300
    assert session.scalar(select(func.count()).select_from(ValidationFinding)) == 1


def test_load_errors(session: Session, seeded: int) -> None:
    service = ValidationService(session)
    with pytest.raises(NotFoundError):
        service.load(seeded, 999)
    with pytest.raises(NotFoundError):
        service.load(999)
    with pytest.raises(NotFoundError):
        service.get_report(999)
    rid = ResumeService(session).create(ResumeCreate(name="Sin perfiles")).id
    for profile in ProfileService(session).list(rid):
        ProfileService(session).delete(profile.id, rid)
    with pytest.raises(ConflictError):
        service.load(rid)


def test_render_for_validation_fallbacks(
    session: Session, seeded: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    cv, profile = ValidationService(session).load(seeded)

    def missing(*_: object, **__: object) -> object:
        raise TemplateNotFound("ats/base.html")

    def broken(_: str) -> int:
        raise RuntimeError("sin motor")

    monkeypatch.setattr("export.pdf.count_pages", broken)
    assert count_pages("<p>x</p>") is None
    html, pages = render_for_validation(cv, profile)
    assert html is not None and pages is None
    assert render_for_validation(cv, profile, with_pages=False)[1] is None
    monkeypatch.setattr(validation_module, "render", missing)
    assert render_for_validation(cv, profile) == (None, None)


# ------------------------------------------------------------------ API


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    api = create_app()

    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    api.dependency_overrides[get_session] = _session
    with TestClient(api) as c:
        yield c


def test_validate_endpoint(client: TestClient, session: Session, seeded: int) -> None:
    session.commit()
    pid = _profile_id(session, seeded, Destination.ATS)
    r = client.post(f"/api/resumes/{seeded}/validate", params={"profile_id": pid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"id", "score", "errors", "warnings", "findings", "created_at"}
    assert body["errors"] == 0 and body["score"] >= 90
    finding = body["findings"][0]
    assert set(finding) >= {"rule_id", "severity", "message", "entity", "entity_id", "suggestion"}
    assert client.post(f"/api/resumes/{seeded}/validate").status_code == 200
    assert client.post("/api/resumes/999/validate").status_code == 404
    r = client.post(f"/api/resumes/{seeded}/validate", params={"profile_id": 999})
    assert r.status_code == 404


def test_validate_endpoint_empty_resume(client: TestClient) -> None:
    rid = client.post("/api/resumes", json={"name": "Nuevo"}).json()["id"]
    body = client.post(f"/api/resumes/{rid}/validate").json()
    assert body["errors"] > 0
    assert body["findings"][0]["severity"] == "error"


# ------------------------------------------------------------------ CLI


@pytest.fixture
def cli_db(session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.db, "get_sessionmaker", lambda: session_factory)


def test_cli_validate(cli_db: None, session: Session, seeded: int) -> None:
    session.commit()
    runner = CliRunner()
    result = runner.invoke(cli_app, ["validate", "--resume", str(seeded), "--profile", "ats"])
    assert result.exit_code == 0, result.output
    assert "puntaje" in result.output
    result = runner.invoke(
        cli_app, ["validate", "--resume", str(seeded), "--profile", "Correo", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["errors"] == 0
    result = runner.invoke(cli_app, ["validate", "--resume", str(seeded), "--profile", "nada"])
    assert result.exit_code == 2
    result = runner.invoke(cli_app, ["validate", "--resume", "999", "--profile", "ats"])
    assert result.exit_code == 2


def test_cli_validate_blocking_errors_exit_1(cli_db: None, session: Session) -> None:
    rid = ResumeService(session).create(ResumeCreate(name="Vacío")).id
    result = CliRunner().invoke(cli_app, ["validate", "--resume", str(rid), "--profile", "ats"])
    assert result.exit_code == 1
    assert "[error] contact.email_present" in result.output
    assert "→" in result.output


def test_cli_rules(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "ATS_RULES.md"
    result = runner.invoke(cli_app, ["rules", "--md", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.read_text(encoding="utf-8") == rules_markdown()
    result = runner.invoke(cli_app, ["rules"])
    assert result.exit_code == 0
    assert "contact.url_plain" in result.output and "mail=-" in result.output
