"""Export profiles and section order/visibility."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Response, status

from app.deps import SessionDep
from schemas import ExportProfileCreate, ExportProfileOut, ExportProfileUpdate, ProfileSectionIn
from services import ProfileService

router = APIRouter(tags=["profiles"])


@router.get("/resumes/{resume_id}/profiles", response_model=list[ExportProfileOut])
def list_profiles(resume_id: int, session: SessionDep) -> list[ExportProfileOut]:
    return [ExportProfileOut.model_validate(p) for p in ProfileService(session).list(resume_id)]


@router.post(
    "/resumes/{resume_id}/profiles",
    response_model=ExportProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    resume_id: int, body: ExportProfileCreate, session: SessionDep
) -> ExportProfileOut:
    return ExportProfileOut.model_validate(ProfileService(session).create(resume_id, body))


@router.get("/resumes/{resume_id}/profiles/{profile_id}", response_model=ExportProfileOut)
def get_profile(resume_id: int, profile_id: int, session: SessionDep) -> ExportProfileOut:
    return ExportProfileOut.model_validate(ProfileService(session).get(profile_id, resume_id))


@router.patch("/resumes/{resume_id}/profiles/{profile_id}", response_model=ExportProfileOut)
def update_profile(
    resume_id: int, profile_id: int, body: ExportProfileUpdate, session: SessionDep
) -> ExportProfileOut:
    profile = ProfileService(session).update(profile_id, body, resume_id)
    return ExportProfileOut.model_validate(profile)


@router.delete("/resumes/{resume_id}/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(resume_id: int, profile_id: int, session: SessionDep) -> Response:
    ProfileService(session).delete(profile_id, resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/profiles/{profile_id}/sections", response_model=ExportProfileOut)
def put_sections(
    profile_id: int,
    sections: Annotated[list[ProfileSectionIn], Body()],
    session: SessionDep,
) -> ExportProfileOut:
    """Full order + visibility + titles of the 7 sections (array order = position)."""
    return ExportProfileOut.model_validate(
        ProfileService(session).set_sections(profile_id, sections)
    )
