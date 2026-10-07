"""Editor pages and HTMX fragments (``/`` and ``/ui/...``).

Contract: ``docs/design/EDITOR_CONTEXT.md``. Every route reuses ``services/`` and the
``*Create``/``*Update`` schemas; nothing is validated twice.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from jinja2 import TemplateNotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import SessionDep
from app.routers import ui_items
from app.routers.exports import EngineDep, _result
from app.web import (
    UiValidationError,
    field_errors,
    form_to_model,
    html,
    merged,
    read_form,
    redirect,
    ui_errors,
    written,
)
from models import ValidationReport
from models.enums import Density, Destination, Severity
from render.renderer import render
from schemas import (
    BasicsUpdate,
    ExportProfileCreate,
    ExportProfileOut,
    ExportProfileUpdate,
    ResumeCreate,
    ResumeOut,
    ResumeSummaryOut,
    ResumeUpdate,
)
from schemas.export import ExportRequest
from schemas.validation import FindingOut, ValidationReportOut
from services import ProfileService, ResumeService
from services.asset import AssetService
from services.errors import ConflictError, InvalidDataError, NotFoundError
from services.export import ExportService
from services.validation import ValidationService

router = APIRouter(tags=["ui"])
router.include_router(ui_items.router)

#: Sections that ``GET /ui/resumes/{id}/sections/{key}`` can re-paint (contract §4.3).
SECTION_KEYS = frozenset(
    {
        "basics",
        "links",
        "experience",
        "education",
        "skills",
        "projects",
        "certifications",
        "languages",
    }
)

#: Grouping order of the validation panel (contract §4.5); unknown sections go last.
SECTION_ORDER = (
    "basics",
    "links",
    "summary",
    "experience",
    "achievement",
    "education",
    "skills",
    "projects",
    "certifications",
    "languages",
    "profile",
    "doc",
    "pdf",
    "export",
    "all",
)
SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}

NO_PROFILES = "El CV no tiene perfiles de exportación"
NO_TEMPLATE = "Plantilla de render aún no disponible"
LAST_PROFILE = "No puedes borrar el único perfil del CV"
NO_FILE = "No se recibió ninguna imagen"


# --------------------------------------------------------------------------------- helpers


def photo_url(resume: ResumeOut) -> str | None:
    """``/ui/assets/{id}?v=<sha>`` of the current photo, or None (contract §4.2)."""
    photo = resume.basics.photo
    if photo is None:
        return None
    return f"/ui/assets/{photo.id}?v={photo.sha256[:8]}"


def resume_context(session: Session, resume_id: int, profile_id: int | None) -> dict[str, Any]:
    """``resume``, ``profiles`` and ``active_profile`` (contract §3)."""
    resume = ResumeService(session).get_out(resume_id)
    profiles = resume.profiles
    if profile_id is not None:
        active = ExportProfileOut.model_validate(ProfileService(session).get(profile_id, resume_id))
    elif profiles:
        active = profiles[0]
    else:
        raise ConflictError(NO_PROFILES)
    return {"resume": resume, "profiles": profiles, "active_profile": active}


def _profile_for(
    session: Session, resume_id: int, profile_id: int | None, density: Density | None
) -> ExportProfileOut:
    profile = ValidationService(session).load(resume_id, profile_id)[1]
    return profile if density is None else profile.model_copy(update={"density": density})


def sort_findings(findings: list[FindingOut]) -> list[FindingOut]:
    """By section (editor order) and then severity: error, warning, info (contract §4.5)."""

    def key(finding: FindingOut) -> tuple[int, str, int, str]:
        section = finding.section or ""
        rank = SECTION_ORDER.index(section) if section in SECTION_ORDER else len(SECTION_ORDER)
        return (rank, section, SEVERITY_RANK.get(finding.severity, 9), finding.rule_id)

    return sorted(findings, key=key)


def last_report(session: Session, resume_id: int, profile_id: int) -> ValidationReportOut | None:
    """Most recent persisted report of the profile (export modal, contract §4.6)."""
    row = session.scalar(
        select(ValidationReport)
        .where(
            ValidationReport.resume_id == resume_id,
            ValidationReport.profile_id == profile_id,
        )
        .order_by(ValidationReport.id.desc())
        .limit(1)
    )
    return None if row is None else ValidationReportOut.model_validate(row)


def basics_response(
    session: Session,
    resume_id: int,
    *,
    errors: dict[str, str] | None = None,
    values: dict[str, Any] | None = None,
) -> Response:
    """``editor/section_basics.html``: 200 + ``cv-changed``, or 422 with the sent values."""
    resume = ResumeService(session).get_out(resume_id)
    context: dict[str, Any] = {
        "resume": resume,
        "photo_url": photo_url(resume),
        "errors": errors or {},
        "open": True,
    }
    if errors:
        context["resume"] = resume.model_copy(
            update={"basics": merged(resume.basics, values or {})}
        )
        return html("editor/section_basics.html", context, status=422)
    return written("editor/section_basics.html", context)


# --------------------------------------------------------------------------------- §3 pages


@router.get("/", name="ui_home")
@ui_errors
async def home(session: SessionDep) -> Response:
    """List of resumes."""
    resumes = [ResumeSummaryOut.model_validate(r) for r in ResumeService(session).list()]
    return html("index.html", {"resumes": resumes})


@router.get("/resumes/{resume_id}/edit", name="ui_edit")
@ui_errors
async def edit_page(
    resume_id: int,
    session: SessionDep,
    profile_id: Annotated[int | None, Query()] = None,
    density: Annotated[Density | None, Query()] = None,
) -> Response:
    """Editor page. The preview loads itself from ``#toolbar`` (contract §3)."""
    context = resume_context(session, resume_id, profile_id)
    active: ExportProfileOut = context["active_profile"]
    context["density"] = (density or active.density).value
    context["photo_url"] = photo_url(context["resume"])
    return html("editor/index.html", context)


@router.get("/resumes/{resume_id}/profiles", name="ui_profiles_page")
@ui_errors
async def profiles_page(
    resume_id: int,
    session: SessionDep,
    profile_id: Annotated[int | None, Query()] = None,
) -> Response:
    return html("editor/profiles.html", resume_context(session, resume_id, profile_id))


# --------------------------------------------------------------------------- §4.1 resume list


def _resume_list(session: Session) -> Response:
    resumes = [ResumeSummaryOut.model_validate(r) for r in ResumeService(session).list()]
    return written("partials/resume_list.html", {"resumes": resumes})


@router.post("/ui/resumes", name="ui_create_resume")
@ui_errors
async def create_resume(request: Request, session: SessionDep) -> Response:
    form = read_form(await request.form())
    created = ResumeService(session).create(form_to_model(form, ResumeCreate))
    return redirect(f"/resumes/{created.id}/edit")


@router.post("/ui/resumes/{resume_id}/duplicate", name="ui_duplicate_resume")
@ui_errors
async def duplicate_resume(resume_id: int, session: SessionDep) -> Response:
    ResumeService(session).duplicate(resume_id)
    return _resume_list(session)


@router.post("/ui/resumes/{resume_id}/default", name="ui_default_resume")
@ui_errors
async def default_resume(resume_id: int, session: SessionDep) -> Response:
    ResumeService(session).update(resume_id, ResumeUpdate(is_default=True))
    return _resume_list(session)


@router.delete("/ui/resumes/{resume_id}", name="ui_delete_resume")
@ui_errors
async def delete_resume(resume_id: int, session: SessionDep) -> Response:
    ResumeService(session).delete(resume_id)
    return _resume_list(session)


# ------------------------------------------------------------------------ §4.2 basics + photo


@router.put("/ui/resumes/{resume_id}/basics", name="ui_update_basics")
@ui_errors
async def update_basics(resume_id: int, request: Request, session: SessionDep) -> Response:
    service = ResumeService(session)
    service.get(resume_id)
    form = read_form(await request.form())
    try:
        service.update_basics(resume_id, form_to_model(form, BasicsUpdate))
    except (UiValidationError, InvalidDataError) as exc:
        errors = exc.errors if isinstance(exc, UiValidationError) else field_errors(exc)
        return basics_response(session, resume_id, errors=errors, values=form.values)
    return basics_response(session, resume_id)


@router.post("/ui/resumes/{resume_id}/photo", name="ui_upload_photo")
@ui_errors
async def upload_photo(resume_id: int, request: Request, session: SessionDep) -> Response:
    """Multipart ``file``. Invalid mime/size → 400 plain text (contract §4.2)."""
    service = ResumeService(session)
    previous = service.get_basics(resume_id).photo_asset_id
    upload = (await request.form()).get("file")
    if upload is None or isinstance(upload, str):
        return PlainTextResponse(NO_FILE, status_code=400)
    assets = AssetService(session)
    try:
        asset = assets.create(await upload.read(), upload.filename or "foto.jpg")
    except InvalidDataError as exc:
        return PlainTextResponse(exc.errors[0]["msg"], status_code=400)
    service.update_basics(resume_id, BasicsUpdate(photo_asset_id=asset.id))
    if previous is not None and previous != asset.id:
        assets.delete_if_unused(previous)
    return basics_response(session, resume_id)


@router.delete("/ui/resumes/{resume_id}/photo", name="ui_delete_photo")
@ui_errors
async def delete_photo(resume_id: int, session: SessionDep) -> Response:
    service = ResumeService(session)
    previous = service.get_basics(resume_id).photo_asset_id
    service.update_basics(resume_id, BasicsUpdate(photo_asset_id=None))
    if previous is not None:
        AssetService(session).delete_if_unused(previous)
    return basics_response(session, resume_id)


@router.get("/ui/assets/{asset_id}", name="ui_asset_file")
@ui_errors
async def asset_file(asset_id: int, session: SessionDep) -> Response:
    """``_400.jpg`` version of the photo (``?v=`` is only a cache buster)."""
    service = AssetService(session)
    asset = service.get(asset_id)
    return FileResponse(service.render_path(asset), media_type="image/jpeg")


# ----------------------------------------------------------------------------- §4.3 sections


@router.get("/ui/resumes/{resume_id}/sections/{key}", name="ui_section")
@ui_errors
async def section(resume_id: int, key: str, session: SessionDep) -> Response:
    if key not in SECTION_KEYS:
        raise NotFoundError(f"No existe la sección «{key}»")
    resume = ResumeService(session).get_out(resume_id)
    context: dict[str, Any] = {"resume": resume, "errors": {}, "open": False}
    if key == "basics":
        context["photo_url"] = photo_url(resume)
    return html(f"editor/section_{key}.html", context)


# ------------------------------------------------------------------------------ §4.4 preview


@router.get("/ui/resumes/{resume_id}/preview", name="ui_preview")
@ui_errors
async def preview(
    resume_id: int,
    session: SessionDep,
    profile_id: Annotated[int | None, Query()] = None,
    density: Annotated[Density | None, Query()] = None,
) -> Response:
    cv = ResumeService(session).get_out(resume_id)
    profile = _profile_for(session, resume_id, profile_id, density)
    try:
        result = render(cv, profile, for_preview=True, with_pages=True)
    except TemplateNotFound:
        return PlainTextResponse(NO_TEMPLATE, status_code=503)
    return html(
        "partials/preview_frame.html",
        {"preview_html": result.html, "pages": result.pages, "max_pages": profile.max_pages},
    )


# --------------------------------------------------------------------------- §4.5 validation


@router.post("/ui/resumes/{resume_id}/validate", name="ui_validate")
@ui_errors
async def validate(resume_id: int, request: Request, session: SessionDep) -> Response:
    """``density`` is ignored: the report belongs to the profile (contract §4.5)."""
    form = read_form(await request.form())
    raw = form.values.get("profile_id")
    profile_id = int(raw) if raw is not None else None
    service = ValidationService(session)
    profile, report = service.run(resume_id, profile_id, render_html=True)
    saved = service.save_report(resume_id, profile.id, report)
    saved = saved.model_copy(update={"findings": sort_findings(saved.findings)})
    blocked = profile.destination == Destination.ATS and saved.errors > 0
    return written(
        "partials/validation_panel.html",
        {"report": saved, "profile": profile, "blocked": blocked},
    )


# ------------------------------------------------------------------------------- §4.6 export


@router.get("/ui/resumes/{resume_id}/export", name="ui_export_modal")
@ui_errors
async def export_modal(
    resume_id: int,
    session: SessionDep,
    profile_id: Annotated[int | None, Query()] = None,
    density: Annotated[Density | None, Query()] = None,
) -> Response:
    context = resume_context(session, resume_id, profile_id)
    active: ExportProfileOut = context["active_profile"]
    context["report"] = last_report(session, resume_id, active.id)
    return html("partials/export_modal.html", context)


@router.post("/ui/resumes/{resume_id}/export", name="ui_export")
@ui_errors
async def export(
    resume_id: int, request: Request, session: SessionDep, engine: EngineDep
) -> Response:
    form = read_form(await request.form())
    body = form_to_model(form, ExportRequest)
    outcome = ExportService(session, engine=engine).run(
        resume_id, body.profile_id, body.formats, body.with_photo_variant
    )
    result = _result(outcome, [p.name for p in outcome.files])
    return written("partials/export_result.html", {"result": result})


# ----------------------------------------------------------------------------- §4.7 profiles


@router.post("/ui/resumes/{resume_id}/profiles", name="ui_create_profile")
@ui_errors
async def create_profile(resume_id: int, request: Request, session: SessionDep) -> Response:
    """``mail`` without a theme defaults to ``slate`` (contract §4.7)."""
    form = read_form(await request.form())
    if form.values.get("destination") == Destination.MAIL.value:
        form.values.setdefault("theme", "slate")
    created = ProfileService(session).create(resume_id, form_to_model(form, ExportProfileCreate))
    return redirect(f"/resumes/{resume_id}/profiles?profile_id={created.id}")


@router.put("/ui/profiles/{profile_id}", name="ui_update_profile")
@ui_errors
async def update_profile(profile_id: int, request: Request, session: SessionDep) -> Response:
    service = ProfileService(session)
    snapshot = ExportProfileOut.model_validate(service.get(profile_id))
    form = read_form(await request.form())
    try:
        updated = service.update(profile_id, form_to_model(form, ExportProfileUpdate))
    except (UiValidationError, InvalidDataError) as exc:
        errors = exc.errors if isinstance(exc, UiValidationError) else field_errors(exc)
        return html(
            "partials/profile_settings.html",
            {"profile": merged(snapshot, form.values), "errors": errors},
            status=422,
        )
    profile = ExportProfileOut.model_validate(updated)
    return written("partials/profile_settings.html", {"profile": profile, "errors": {}})


@router.delete("/ui/profiles/{profile_id}", name="ui_delete_profile")
@ui_errors
async def delete_profile(profile_id: int, session: SessionDep) -> Response:
    service = ProfileService(session)
    resume_id = service.get(profile_id).resume_id
    if len(service.list(resume_id)) <= 1:
        raise ConflictError(LAST_PROFILE)
    service.delete(profile_id)
    return redirect(f"/resumes/{resume_id}/profiles")
