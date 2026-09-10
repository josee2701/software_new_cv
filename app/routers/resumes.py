"""Resumes, basics, contact links and snapshots."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Response, status

from app.deps import SessionDep
from app.routers.crud import register_ordered_crud
from schemas import (
    BasicsOut,
    BasicsUpdate,
    ContactLinkCreate,
    ContactLinkOut,
    ContactLinkUpdate,
    ResumeCreate,
    ResumeDuplicate,
    ResumeOut,
    ResumeSummaryOut,
    ResumeUpdate,
    SnapshotCreate,
    SnapshotDetailOut,
    SnapshotOut,
)
from services import ResumeService

router = APIRouter(tags=["resumes"])


@router.get("/resumes", response_model=list[ResumeSummaryOut])
def list_resumes(session: SessionDep) -> list[ResumeSummaryOut]:
    return [ResumeSummaryOut.model_validate(r) for r in ResumeService(session).list()]


@router.post("/resumes", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def create_resume(body: ResumeCreate, session: SessionDep) -> ResumeOut:
    service = ResumeService(session)
    return service.get_out(service.create(body).id)


@router.get("/resumes/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, session: SessionDep) -> ResumeOut:
    return ResumeService(session).get_out(resume_id)


@router.patch("/resumes/{resume_id}", response_model=ResumeSummaryOut)
def update_resume(resume_id: int, body: ResumeUpdate, session: SessionDep) -> ResumeSummaryOut:
    return ResumeSummaryOut.model_validate(ResumeService(session).update(resume_id, body))


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, session: SessionDep) -> Response:
    ResumeService(session).delete(resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/resumes/{resume_id}/duplicate",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_resume(
    resume_id: int,
    session: SessionDep,
    body: Annotated[ResumeDuplicate | None, Body()] = None,
) -> ResumeOut:
    service = ResumeService(session)
    clone = service.duplicate(resume_id, body.name if body else None)
    return service.get_out(clone.id)


@router.get("/resumes/{resume_id}/basics", response_model=BasicsOut)
def get_basics(resume_id: int, session: SessionDep) -> BasicsOut:
    return BasicsOut.model_validate(ResumeService(session).get_basics(resume_id))


@router.put("/resumes/{resume_id}/basics", response_model=BasicsOut)
def put_basics(resume_id: int, body: BasicsUpdate, session: SessionDep) -> BasicsOut:
    """Merges only the fields sent (see docs/DECISIONS.md)."""
    return BasicsOut.model_validate(ResumeService(session).update_basics(resume_id, body))


register_ordered_crud(
    router,
    collection="/resumes/{parent_id}/links",
    service=lambda s: ResumeService(s).links,
    create_schema=ContactLinkCreate,
    update_schema=ContactLinkUpdate,
    out_schema=ContactLinkOut,
    name="links",
)


@router.post(
    "/resumes/{resume_id}/snapshots",
    response_model=SnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    resume_id: int,
    session: SessionDep,
    body: Annotated[SnapshotCreate | None, Body()] = None,
) -> SnapshotOut:
    snapshot = ResumeService(session).create_snapshot(resume_id, body.label if body else None)
    return SnapshotOut.model_validate(snapshot)


@router.get("/resumes/{resume_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(resume_id: int, session: SessionDep) -> list[SnapshotOut]:
    return [SnapshotOut.model_validate(s) for s in ResumeService(session).list_snapshots(resume_id)]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotDetailOut)
def get_snapshot(snapshot_id: int, session: SessionDep) -> SnapshotDetailOut:
    return SnapshotDetailOut.model_validate(ResumeService(session).get_snapshot(snapshot_id))


@router.post("/snapshots/{snapshot_id}/restore", response_model=ResumeOut)
def restore_snapshot(snapshot_id: int, session: SessionDep) -> ResumeOut:
    """Replace the resume content with the snapshot (one transaction)."""
    service = ResumeService(session)
    resume = service.restore_snapshot(snapshot_id)
    return service.get_out(resume.id)
