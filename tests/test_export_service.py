"""ExportService.run (spec §10) with injectable fake validation engines."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.seed import run_seed
from models import ExportJob, ResumeSnapshot, ValidationFinding, ValidationReport
from models.enums import Destination, ExportFormat, ExportStatus, Severity
from schemas import ExportProfileUpdate
from services import NotFoundError, ProfileService
from services.export import (
    TEXT_EXTRACTABLE,
    ExportService,
    default_engine,
    export_basename,
    null_engine,
)
from services.resume import ResumeService
from validator.types import Finding, Report, RuleContext


class Recorder:
    """Fake engine: records contexts; returns the given report per phase."""

    def __init__(self, pre: Report | None = None, post: Report | None = None) -> None:
        self.pre = pre or Report(score=100)
        self.post = post or Report(score=95)
        self.calls: list[RuleContext] = []

    def __call__(self, ctx: RuleContext) -> Report:
        self.calls.append(ctx)
        return self.post if ctx.pdf is not None else self.pre


def _error(rule_id: str = "contact.email_present") -> Report:
    return Report(
        score=40,
        findings=(Finding(rule_id, Severity.ERROR, "Falta algo", section="basics"),),
    )


def _setup(session: Session) -> tuple[int, int, int]:
    rid = run_seed(session).resume_id
    profiles = {p.destination: p.id for p in ProfileService(session).list(rid)}
    return rid, profiles[Destination.ATS], profiles[Destination.MAIL]


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_export_done_writes_named_files(session: Session, tmp_path: Path) -> None:
    rid, ats, _ = _setup(session)
    engine = Recorder(post=Report(score=92, findings=(
        Finding("content.metric", Severity.WARNING, "Pocas métricas"),
    )))  # fmt: skip
    service = ExportService(session, engine=engine, exports_dir=tmp_path)
    outcome = service.run(rid, ats, [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.JSON])
    job = outcome.job
    assert job.status is ExportStatus.DONE, job.error
    assert [p.name for p in outcome.files] == [
        "Andres_Rojas_CV_ats.pdf", "Andres_Rojas_CV_ats.docx", "Andres_Rojas_CV_ats.json",
    ]  # fmt: skip
    assert all(p.parent == tmp_path / str(job.id) and p.stat().st_size > 0 for p in outcome.files)
    assert job.output_path == str(tmp_path / str(job.id))
    assert job.pages is not None and 1 <= job.pages <= 2
    assert job.roundtrip_ok is True
    assert outcome.pdf_info is not None and outcome.pdf_info.coverage >= 0.95
    # phases: pre without pdf (with html), post with html + pages + pdf
    pre, post = engine.calls
    assert pre.pdf is None and pre.html and "<table" not in pre.html
    assert post.pdf is outcome.pdf_info and post.pages == job.pages and post.html == pre.html
    # persisted report (the full one) + snapshot
    report = session.get(ValidationReport, job.report_id)
    assert report is not None and (report.score, report.warnings) == (92, 1)
    assert [f.rule_id for f in report.findings] == ["content.metric"]
    snapshot = session.get(ResumeSnapshot, job.snapshot_id)
    assert snapshot is not None and snapshot.payload["id"] == rid
    exported = json.loads(outcome.files[2].read_text(encoding="utf-8"))
    assert exported == ResumeService(session).get_out(rid).model_dump(mode="json")
    assert service.file_for(job.id, ExportFormat.DOCX).name == "Andres_Rojas_CV_ats.docx"


def test_pre_validation_error_blocks_ats(session: Session, tmp_path: Path) -> None:
    rid, ats, _ = _setup(session)
    engine = Recorder(pre=_error())
    outcome = ExportService(session, engine=engine, exports_dir=tmp_path).run(rid, ats)
    assert outcome.job.status is ExportStatus.BLOCKED
    assert outcome.files == [] and not (tmp_path / str(outcome.job.id)).exists()
    assert len(engine.calls) == 1  # no PDF generated
    assert outcome.job.snapshot_id is None and _count(session, ResumeSnapshot) == 0
    assert _count(session, ValidationFinding) == 1
    assert "bloqueada" in (outcome.job.error or "")


def test_mail_never_blocks(session: Session, tmp_path: Path) -> None:
    rid, _, mail = _setup(session)
    engine = Recorder(pre=_error(), post=_error(TEXT_EXTRACTABLE))
    outcome = ExportService(session, engine=engine, exports_dir=tmp_path).run(rid, mail)
    assert outcome.job.status is ExportStatus.DONE
    assert [p.name for p in outcome.files] == ["Andres_Rojas_CV_correo.pdf"]


def test_text_extractable_error_fails_ats(session: Session, tmp_path: Path) -> None:
    rid, ats, _ = _setup(session)
    engine = Recorder(post=_error(TEXT_EXTRACTABLE))
    outcome = ExportService(session, engine=engine, exports_dir=tmp_path).run(rid, ats)
    assert outcome.job.status is ExportStatus.FAILED
    assert "extraíble" in (outcome.job.error or "")
    assert outcome.files == []
    assert outcome.job.snapshot_id is not None  # snapshot was taken before rendering


def test_post_validation_error_blocks_ats(session: Session, tmp_path: Path) -> None:
    rid, ats, _ = _setup(session)
    engine = Recorder(post=_error("length.pages"))
    outcome = ExportService(session, engine=engine, exports_dir=tmp_path).run(rid, ats)
    assert outcome.job.status is ExportStatus.BLOCKED
    assert outcome.job.pages is not None and outcome.files == []


def test_mail_photo_variant(session: Session, tmp_path: Path) -> None:
    rid, _, mail = _setup(session)
    ProfileService(session).update(mail, ExportProfileUpdate(include_photo=True))
    service = ExportService(session, engine=Recorder(), exports_dir=tmp_path)
    outcome = service.run(rid, mail, [ExportFormat.PDF], with_photo_variant=True)
    names = [p.name for p in outcome.files]
    assert names == ["Andres_Rojas_CV_correo.pdf", "Andres_Rojas_CV_correo_sinfoto.pdf"]
    job_id = outcome.job.id
    assert service.file_for(job_id, ExportFormat.PDF).name == names[0]
    assert service.file_for(job_id, ExportFormat.PDF, "sinfoto").name == names[1]
    with pytest.raises(NotFoundError):
        service.file_for(job_id, ExportFormat.DOCX)
    with pytest.raises(NotFoundError):
        service.get_job(999)


def test_pdf_engine_error_marks_failed(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rid, ats, _ = _setup(session)
    monkeypatch.setenv("CV_ATS_PDF_ENGINE", "playwright")
    from app.config import get_settings

    get_settings.cache_clear()
    if importlib.util.find_spec("playwright") is not None:
        pytest.skip("Playwright instalado")
    outcome = ExportService(session, engine=Recorder(), exports_dir=tmp_path).run(rid, ats)
    assert outcome.job.status is ExportStatus.FAILED
    assert "Playwright" in (outcome.job.error or "")


def test_unexpected_error_marks_failed(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rid, ats, _ = _setup(session)

    def broken(ctx: RuleContext) -> Report:
        raise RuntimeError("motor roto")

    outcome = ExportService(session, engine=broken, exports_dir=tmp_path).run(rid, ats)
    assert outcome.job.status is ExportStatus.FAILED
    assert outcome.job.error == "motor roto"
    assert session.get(ExportJob, outcome.job.id) is not None


def test_basename_and_default_engine(session: Session) -> None:
    rid, _, _ = _setup(session)
    cv = ResumeService(session).get_out(rid)
    assert export_basename(cv, cv.profiles[0]) == "Andres_Rojas_CV_ats"
    assert export_basename(cv, cv.profiles[1]) == "Andres_Rojas_CV_correo"
    assert null_engine(RuleContext(cv=cv, profile=cv.profiles[0])).score == 100
    engine = default_engine()
    if importlib.util.find_spec("validator.engine") is None:
        assert engine is null_engine
    else:
        assert callable(engine)
