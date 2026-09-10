"""Snapshots: create and restore with exact round-trip (spec §4.4, F2-07)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.seed import run_seed
from models import ExportJob, ExportProfile
from models.enums import Destination, ExportFormat, LanguageLevel, SectionKey
from schemas import (
    BasicsUpdate,
    ExportProfileCreate,
    ExportProfileUpdate,
    LanguageCreate,
    ProfileSectionIn,
    ResumeUpdate,
)
from services import (
    EducationService,
    ExperienceService,
    LanguageService,
    NotFoundError,
    ProfileService,
    ResumeService,
)

# Restore recreates content rows: ids and timestamps change by design (DECISIONS.md).
IGNORED = {"id", "created_at", "updated_at"}


def _strip(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _strip(v) for k, v in data.items() if k not in IGNORED}
    if isinstance(data, list):
        return [_strip(v) for v in data]
    return data


def _dump(session: Session, rid: int) -> dict[str, Any]:
    dumped: dict[str, Any] = ResumeService(session).get_out(rid).model_dump(mode="json")
    return dumped


def _mutate(session: Session, rid: int) -> None:
    ResumeService(session).update(rid, ResumeUpdate(notes="cambiado", language="en"))
    ResumeService(session).update_basics(rid, BasicsUpdate(full_name="Otra Persona"))
    experiences = ExperienceService(session)
    exps = experiences.list(rid)
    experiences.delete(exps[-1].id)
    experiences.set_technologies(exps[0].id, ["Rust"])
    ach = exps[0].achievements[0]
    experiences.achievements.delete(ach.id)
    edu = EducationService(session)
    edu.reorder(rid, [e.id for e in reversed(edu.list(rid))])
    LanguageService(session).create(rid, LanguageCreate(name="Francés", level=LanguageLevel.A2))
    profiles = ProfileService(session)
    mail = next(p for p in profiles.list(rid) if p.destination is Destination.MAIL)
    profiles.update(mail.id, ExportProfileUpdate(theme="ocean", accent_color="#112233"))
    profiles.set_sections(
        mail.id,
        [
            ProfileSectionIn(section=k, visible=k != SectionKey.PROJECTS)
            for k in reversed(SectionKey)
        ],
    )


def test_snapshot_restore_round_trip(session: Session) -> None:
    rid = run_seed(session).resume_id
    service = ResumeService(session)
    original = _dump(session, rid)
    snap = service.create_snapshot(rid, "antes")
    _mutate(session, rid)
    assert _strip(_dump(session, rid)) != _strip(original)

    service.restore_snapshot(snap.id)
    restored = _dump(session, rid)
    assert _strip(restored) == _strip(original)
    # profiles are updated in place: their ids survive
    assert [p["id"] for p in restored["profiles"]] == [p["id"] for p in original["profiles"]]
    assert restored["basics"]["id"] == original["basics"]["id"]


def test_restore_keeps_profiles_with_export_jobs(session: Session) -> None:
    rid = run_seed(session).resume_id
    service = ResumeService(session)
    snap = service.create_snapshot(rid)
    profiles = ProfileService(session)
    extra_free = profiles.create(
        rid, ExportProfileCreate(name="Libre", destination=Destination.ATS)
    )
    extra_used = profiles.create(
        rid, ExportProfileCreate(name="Usado", destination=Destination.ATS)
    )
    existing = profiles.list(rid)[0]
    session.add_all([
        ExportJob(resume_id=rid, profile_id=extra_used.id, format=ExportFormat.PDF),
        ExportJob(resume_id=rid, profile_id=existing.id, format=ExportFormat.PDF),
    ])  # fmt: skip
    session.commit()
    service.restore_snapshot(snap.id)
    names = {p.name for p in profiles.list(rid)}
    assert names == {"Plataforma", "Correo", "Usado"}
    assert session.get(ExportProfile, extra_free.id) is None
    assert session.scalar(select(func.count()).select_from(ExportJob)) == 2


def test_restore_does_not_steal_a_taken_name(session: Session) -> None:
    from schemas import ResumeCreate

    rid = run_seed(session).resume_id
    service = ResumeService(session)
    snap = service.create_snapshot(rid)
    old_name = service.get(rid).name
    service.update(rid, ResumeUpdate(name="Nuevo nombre"))
    service.create(ResumeCreate(name=old_name))
    service.restore_snapshot(snap.id)
    assert service.get(rid).name == "Nuevo nombre"


def test_restore_missing_snapshot(session: Session) -> None:
    with pytest.raises(NotFoundError):
        ResumeService(session).restore_snapshot(999)
