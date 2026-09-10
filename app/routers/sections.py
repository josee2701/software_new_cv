"""Education, projects, certifications, languages and skills."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.deps import SessionDep
from app.routers.crud import register_ordered_crud
from schemas import (
    CertificationCreate,
    CertificationOut,
    CertificationUpdate,
    EducationCreate,
    EducationOut,
    EducationUpdate,
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
    LanguageService,
    ProjectService,
    SkillService,
)

router = APIRouter(tags=["sections"])

register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/education",
    service=EducationService,
    create_schema=EducationCreate,
    update_schema=EducationUpdate,
    out_schema=EducationOut,
    name="education",
)
register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/projects",
    service=ProjectService,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    out_schema=ProjectOut,
    name="projects",
)
register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/certifications",
    service=CertificationService,
    create_schema=CertificationCreate,
    update_schema=CertificationUpdate,
    out_schema=CertificationOut,
    name="certifications",
)
register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/languages",
    service=LanguageService,
    create_schema=LanguageCreate,
    update_schema=LanguageUpdate,
    out_schema=LanguageOut,
    name="languages",
)
register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/skill-categories",
    service=SkillService,
    create_schema=SkillCategoryCreate,
    update_schema=SkillCategoryUpdate,
    out_schema=SkillCategoryOut,
    name="skill_categories",
)
register_ordered_crud(
    router,
    collection="/skill-categories/{parent_id}/skills",
    service=lambda s: SkillService(s).skills,
    create_schema=SkillCreate,
    update_schema=SkillUpdate,
    out_schema=SkillOut,
    name="skills",
)


@router.put("/projects/{project_id}/technologies", response_model=list[str])
def set_project_technologies(
    project_id: int,
    names: Annotated[list[str], Body(max_length=40)],
    session: SessionDep,
) -> list[str]:
    return ProjectService(session).set_technologies(project_id, names)
