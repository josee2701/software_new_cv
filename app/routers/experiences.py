"""Experiences, achievements and experience technologies."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body

from app.deps import SessionDep
from app.routers.crud import register_ordered_crud
from schemas import (
    AchievementCreate,
    AchievementOut,
    AchievementUpdate,
    ExperienceCreate,
    ExperienceOut,
    ExperienceUpdate,
)
from services import ExperienceService

router = APIRouter(tags=["experiences"])

register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/experiences",
    service=ExperienceService,
    create_schema=ExperienceCreate,
    update_schema=ExperienceUpdate,
    out_schema=ExperienceOut,
    name="experiences",
)
register_ordered_crud(
    router,
    collection="/experiences/{parent_id}/achievements",
    service=lambda s: ExperienceService(s).achievements,
    create_schema=AchievementCreate,
    update_schema=AchievementUpdate,
    out_schema=AchievementOut,
    name="achievements",
)


@router.put("/experiences/{experience_id}/technologies", response_model=list[str])
def set_experience_technologies(
    experience_id: int,
    names: Annotated[list[str], Body(max_length=40)],
    session: SessionDep,
) -> list[str]:
    """Ordered list of names → get_or_create in the catalog. Returns canonical names."""
    return ExperienceService(session).set_technologies(experience_id, names)
