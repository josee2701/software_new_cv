"""Job postings: keywords and CV match (spec §12)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import SessionDep
from schemas.match import MatchResultOut, PostingCreate
from services.match import MatchService

router = APIRouter(tags=["match"])


@router.post(
    "/resumes/{resume_id}/postings",
    response_model=MatchResultOut,
    status_code=status.HTTP_201_CREATED,
)
def create_posting(resume_id: int, body: PostingCreate, session: SessionDep) -> MatchResultOut:
    """Paste a job posting → top keywords (technologies first) and what the CV covers."""
    return MatchService(session).create_posting(resume_id, body)


@router.get("/postings/{posting_id}/match", response_model=MatchResultOut)
def posting_match(posting_id: int, session: SessionDep) -> MatchResultOut:
    """Present / missing keywords, recomputed against the current CV."""
    return MatchService(session).match(posting_id)
