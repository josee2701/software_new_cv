"""Shared helpers for export tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.seed import run_seed
from models.enums import Destination
from schemas import ExportProfileOut, ResumeOut
from services import ResumeService


def seeded_cv(session: Session) -> ResumeOut:
    return ResumeService(session).get_out(run_seed(session).resume_id)


def profile_of(cv: ResumeOut, destination: Destination) -> ExportProfileOut:
    return next(p for p in cv.profiles if p.destination is destination)
