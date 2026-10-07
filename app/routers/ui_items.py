"""Generic HTMX item routes of the editor (contract §4.3).

One table drives the nine ordered collections: ``GET .../new`` (unsaved draft), ``POST`` (create),
``PUT`` (partial update) and ``DELETE``. Every route reuses the existing services and schemas.

Note: no ``from __future__ import annotations`` here — FastAPI must see the real types of the
endpoint signatures built inside the factory.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import SessionDep
from app.web import (
    UiValidationError,
    deleted,
    draft,
    field_errors,
    form_to_model,
    html,
    merged,
    read_form,
    ui_errors,
    written,
)
from schemas import (
    AchievementCreate,
    AchievementOut,
    AchievementUpdate,
    CertificationCreate,
    CertificationOut,
    CertificationUpdate,
    ContactLinkCreate,
    ContactLinkOut,
    ContactLinkUpdate,
    EducationCreate,
    EducationOut,
    EducationUpdate,
    ExperienceCreate,
    ExperienceOut,
    ExperienceUpdate,
    LanguageCreate,
    LanguageOut,
    LanguageUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    SkillCategoryCreate,
    SkillCategoryOut,
    SkillCategoryUpdate,
    SkillCreate,
    SkillOut,
    SkillUpdate,
)
from services import (
    CertificationService,
    EducationService,
    ExperienceService,
    LanguageService,
    ProjectService,
    ResumeService,
    SkillService,
)
from services.base import ChildService
from services.errors import InvalidDataError

router = APIRouter(tags=["ui"])


@dataclass(frozen=True)
class ItemSpec:
    """One row of the table in contract §4.3."""

    coll: str  # URL segment of the collection
    parent: str  # URL segment of the parent collection
    parent_key: str  # name of the parent id in the template context
    template: str
    create: type[BaseModel]
    update: type[BaseModel]
    out: type[BaseModel]
    service: Callable[[Session], ChildService[Any]]
    draft_extra: dict[str, Any] = field(default_factory=dict)


SPECS: tuple[ItemSpec, ...] = (
    ItemSpec(
        "links",
        "resumes",
        "resume_id",
        "editor/item_link.html",
        ContactLinkCreate,
        ContactLinkUpdate,
        ContactLinkOut,
        lambda s: ResumeService(s).links,
        {"kind": "linkedin"},
    ),
    ItemSpec(
        "experiences",
        "resumes",
        "resume_id",
        "editor/item_experience.html",
        ExperienceCreate,
        ExperienceUpdate,
        ExperienceOut,
        ExperienceService,
    ),
    ItemSpec(
        "achievements",
        "experiences",
        "experience_id",
        "editor/item_achievement.html",
        AchievementCreate,
        AchievementUpdate,
        AchievementOut,
        lambda s: ExperienceService(s).achievements,
    ),
    ItemSpec(
        "education",
        "resumes",
        "resume_id",
        "editor/item_education.html",
        EducationCreate,
        EducationUpdate,
        EducationOut,
        EducationService,
    ),
    ItemSpec(
        "skill-categories",
        "resumes",
        "resume_id",
        "editor/item_skill_category.html",
        SkillCategoryCreate,
        SkillCategoryUpdate,
        SkillCategoryOut,
        SkillService,
    ),
    ItemSpec(
        "skills",
        "skill-categories",
        "category_id",
        "editor/item_skill.html",
        SkillCreate,
        SkillUpdate,
        SkillOut,
        lambda s: SkillService(s).skills,
    ),
    ItemSpec(
        "projects",
        "resumes",
        "resume_id",
        "editor/item_project.html",
        ProjectCreate,
        ProjectUpdate,
        ProjectOut,
        ProjectService,
    ),
    ItemSpec(
        "certifications",
        "resumes",
        "resume_id",
        "editor/item_certification.html",
        CertificationCreate,
        CertificationUpdate,
        CertificationOut,
        CertificationService,
    ),
    ItemSpec(
        "languages",
        "resumes",
        "resume_id",
        "editor/item_language.html",
        LanguageCreate,
        LanguageUpdate,
        LanguageOut,
        LanguageService,
        {"level": "B2"},
    ),
)

SPEC_BY_COLL = {spec.coll: spec for spec in SPECS}


def context(spec: ItemSpec, item: Any, parent_id: int, errors: dict[str, str], open: bool) -> Any:
    """Default context of every item partial (contract §2.3)."""
    return {"item": item, spec.parent_key: parent_id, "errors": errors, "open": open}


def _register(spec: ItemSpec) -> None:
    coll, parent = spec.coll, spec.parent

    @router.get(f"/ui/{parent}/{{parent_id}}/{coll}/new", name=f"ui_new_{coll}")
    @ui_errors
    async def new_item(parent_id: int, session: SessionDep) -> Response:
        """Unsaved draft: the template shows it as "new" because ``item.id`` is None."""
        spec.service(session).require_parent(parent_id)
        item = draft(spec.out, **spec.draft_extra)
        return html(spec.template, context(spec, item, parent_id, {}, True))

    @router.post(f"/ui/{parent}/{{parent_id}}/{coll}", name=f"ui_create_{coll}")
    @ui_errors
    async def create_item(parent_id: int, request: Request, session: SessionDep) -> Response:
        service = spec.service(session)
        service.require_parent(parent_id)
        form = read_form(await request.form())
        try:
            created = service.create(parent_id, form_to_model(form, spec.create))
        except (UiValidationError, InvalidDataError) as exc:
            errors = exc.errors if isinstance(exc, UiValidationError) else field_errors(exc)
            item = merged(draft(spec.out, **spec.draft_extra), form.values)
            return html(spec.template, context(spec, item, parent_id, errors, True), status=422)
        out = spec.out.model_validate(created)
        return written(spec.template, context(spec, out, parent_id, {}, True))

    @router.put(f"/ui/{coll}/{{item_id}}", name=f"ui_update_{coll}")
    @ui_errors
    async def update_item(item_id: int, request: Request, session: SessionDep) -> Response:
        service = spec.service(session)
        current = service.get(item_id)
        parent_id = service.parent_of(current)
        snapshot = spec.out.model_validate(current)
        form = read_form(await request.form())
        try:
            updated = service.update(item_id, form_to_model(form, spec.update))
        except (UiValidationError, InvalidDataError) as exc:
            errors = exc.errors if isinstance(exc, UiValidationError) else field_errors(exc)
            item = merged(snapshot, form.values)
            return html(spec.template, context(spec, item, parent_id, errors, True), status=422)
        out = spec.out.model_validate(updated)
        return written(spec.template, context(spec, out, parent_id, {}, form.open))

    @router.delete(f"/ui/{coll}/{{item_id}}", name=f"ui_delete_{coll}")
    @ui_errors
    async def delete_item(item_id: int, session: SessionDep) -> Response:
        spec.service(session).delete(item_id)
        return deleted()


for _spec in SPECS:
    _register(_spec)
