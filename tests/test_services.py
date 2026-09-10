"""Service-layer rules (spec §4.5, §14)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import ExportJob, ExportProfile, ProfileSection, Resume, Technology
from models.enums import Destination, ExportFormat, LinkKind, SectionKey, ShowIn
from schemas import (
    AchievementCreate,
    AchievementUpdate,
    BasicsUpdate,
    CertificationCreate,
    ContactLinkCreate,
    ContactLinkUpdate,
    EducationCreate,
    ExperienceCreate,
    ExperienceUpdate,
    ExportProfileCreate,
    ExportProfileUpdate,
    LanguageCreate,
    ProfileSectionIn,
    ProjectCreate,
    ResumeCreate,
    ResumeOut,
    ResumeUpdate,
    SkillCategoryCreate,
    SkillCreate,
)
from services import (
    CertificationService,
    ConflictError,
    EducationService,
    ExperienceService,
    InvalidDataError,
    LanguageService,
    NotFoundError,
    ProfileService,
    ProjectService,
    ResumeService,
    SkillService,
    TechnologyService,
)
from services.profile import DEFAULT_SECTION_ORDER


def _new_resume(session: Session, name: str = "General", **kw: object) -> Resume:
    return ResumeService(session).create(ResumeCreate(name=name, **kw))  # type: ignore[arg-type]


def _exp(
    session: Session, resume_id: int, start: str, end: str | None = None, company: str = "ACME"
) -> int:
    data = ExperienceCreate(
        company=company,
        role="Dev",
        start_date=start,  # type: ignore[arg-type]
        end_date=end,
        is_current=end is None,  # type: ignore[arg-type]
    )
    return ExperienceService(session).create(resume_id, data).id


# ------------------------------------------------------------------------ resume


def test_create_resume_builds_basics_profiles_and_sections(session: Session) -> None:
    resume = _new_resume(session)
    out = ResumeService(session).get_out(resume.id)
    assert out.basics.full_name == ""
    assert out.basics.country == "CO"
    assert [p.name for p in out.profiles] == ["Plataforma", "Correo"]
    ats, mail = out.profiles
    assert ats.destination == Destination.ATS and ats.theme is None
    assert mail.destination == Destination.MAIL and mail.theme == "slate"
    for profile in out.profiles:
        assert [s.section for s in profile.sections] == list(DEFAULT_SECTION_ORDER)
        assert [s.position for s in profile.sections] == list(range(7))
    assert session.scalar(select(func.count()).select_from(ProfileSection)) == 14


def test_resume_name_unique(session: Session) -> None:
    _new_resume(session, "General")
    with pytest.raises(ConflictError):
        _new_resume(session, "general")


def test_is_default_unique(session: Session) -> None:
    service = ResumeService(session)
    a = _new_resume(session, "A", is_default=True)
    b = _new_resume(session, "B", is_default=True)
    session.expire_all()
    assert (a.is_default, b.is_default) == (False, True)
    service.update(a.id, ResumeUpdate(is_default=True))
    session.expire_all()
    assert (a.is_default, b.is_default) == (True, False)
    assert service.list()[0].id == a.id


def test_update_resume_rejects_null_name(session: Session) -> None:
    resume = _new_resume(session)
    with pytest.raises(InvalidDataError):
        ResumeService(session).update(resume.id, ResumeUpdate(name=None))


def test_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError):
        ResumeService(session).get(999)
    with pytest.raises(NotFoundError):
        ExperienceService(session).list(999)


def test_delete_resume_cascades(session: Session) -> None:
    resume = _new_resume(session)
    _exp(session, resume.id, "2020-01", "2021-01")
    ResumeService(session).delete(resume.id)
    assert session.scalar(select(func.count()).select_from(ExportProfile)) == 0


# ------------------------------------------------------------------------ basics / links


def test_update_basics_partial_and_phone(session: Session) -> None:
    resume = _new_resume(session)
    service = ResumeService(session)
    service.update_basics(resume.id, BasicsUpdate(full_name="Ana Gómez"))
    basics = service.update_basics(resume.id, BasicsUpdate(phone="300 123 4567"))
    assert basics.full_name == "Ana Gómez"
    assert basics.phone == "+573001234567"
    with pytest.raises(InvalidDataError):
        service.update_basics(resume.id, BasicsUpdate(photo_asset_id=42))
    with pytest.raises(InvalidDataError):
        service.update_basics(resume.id, BasicsUpdate(full_name=None))


def test_link_kind_unique_except_other(session: Session) -> None:
    resume = _new_resume(session)
    links = ResumeService(session).links
    gh = links.create(resume.id, ContactLinkCreate(kind=LinkKind.GITHUB, url="github.com/ana"))
    assert gh.url == "https://github.com/ana"
    with pytest.raises(ConflictError):
        links.create(resume.id, ContactLinkCreate(kind=LinkKind.GITHUB, url="https://x.io"))
    links.create(resume.id, ContactLinkCreate(kind=LinkKind.OTHER, url="https://a.io"))
    other = links.create(resume.id, ContactLinkCreate(kind=LinkKind.OTHER, url="https://b.io"))
    with pytest.raises(ConflictError):
        links.update(other.id, ContactLinkUpdate(kind=LinkKind.GITHUB), resume.id)
    assert [link.position for link in links.list(resume.id)] == [0, 1, 2]


# ------------------------------------------------------------------------ ordering


def test_reorder_is_atomic_and_compact(session: Session) -> None:
    resume = _new_resume(session)
    service = EducationService(session)
    ids = [
        service.create(resume.id, EducationCreate(institution=f"U{i}", degree="Ing")).id
        for i in range(3)
    ]
    new_order = [ids[2], ids[0], ids[1]]
    items = service.reorder(resume.id, new_order)
    assert [e.id for e in items] == new_order
    assert [e.position for e in items] == [0, 1, 2]

    with pytest.raises(InvalidDataError):
        service.reorder(resume.id, [ids[0], ids[1]])
    with pytest.raises(InvalidDataError):
        service.reorder(resume.id, [ids[0], ids[0], ids[1]])
    assert [e.id for e in service.list(resume.id)] == new_order  # unchanged after errors

    service.delete(ids[0], resume.id)
    remaining = service.list(resume.id)
    assert [e.id for e in remaining] == [ids[2], ids[1]]
    assert [e.position for e in remaining] == [0, 1]


def test_experiences_default_to_reverse_chronological(session: Session) -> None:
    resume = _new_resume(session)
    service = ExperienceService(session)
    old = _exp(session, resume.id, "2015-01", "2017-01", "Old")
    new = _exp(session, resume.id, "2021-01", None, "New")
    mid = _exp(session, resume.id, "2018-01", "2020-12", "Mid")
    assert [e.id for e in service.list(resume.id)] == [new, mid, old]

    # After a manual reorder, new experiences are appended at the end.
    service.reorder(resume.id, [old, new, mid])
    newest = _exp(session, resume.id, "2024-01", "2024-06", "Newest")
    assert [e.id for e in service.list(resume.id)] == [old, new, mid, newest]


def test_experience_update_rules(session: Session) -> None:
    resume = _new_resume(session)
    service = ExperienceService(session)
    exp_id = _exp(session, resume.id, "2020-01", "2021-06")
    exp = service.update(exp_id, ExperienceUpdate(is_current=True))
    assert exp.is_current and exp.end_date is None
    with pytest.raises(InvalidDataError) as info:
        service.update(exp_id, ExperienceUpdate(is_current=False))
    assert info.value.errors[0]["field"] == "end_date"
    with pytest.raises(InvalidDataError):
        service.update(exp_id, ExperienceUpdate(is_current=False, end_date="2019-01"))  # type: ignore[arg-type]
    exp = service.update(exp_id, ExperienceUpdate(is_current=False, end_date="2022-02-17"))  # type: ignore[arg-type]
    assert exp.end_date == date(2022, 2, 1)


def test_achievements_crud_and_order(session: Session) -> None:
    resume = _new_resume(session)
    service = ExperienceService(session)
    exp_id = _exp(session, resume.id, "2020-01", "2021-06")
    a1 = service.achievements.create(exp_id, AchievementCreate(text="• Reduje  costos 20%"))
    a2 = service.achievements.create(exp_id, AchievementCreate(text="- Lideré un equipo de 5"))
    assert a1.text == "Reduje costos 20%"
    service.achievements.reorder(exp_id, [a2.id, a1.id])
    service.achievements.update(a1.id, AchievementUpdate(show_in=ShowIn.MAIL), exp_id)
    out = ResumeService(session).get_out(resume.id)
    texts = [a.text for a in out.experiences[0].achievements]
    assert texts == ["Lideré un equipo de 5", "Reduje costos 20%"]
    assert out.experiences[0].achievements[1].show_in == ShowIn.MAIL
    with pytest.raises(NotFoundError):
        service.achievements.get(a1.id, parent_id=exp_id + 100)


# ------------------------------------------------------------------------ technologies


def test_technology_get_or_create_normalizes(session: Session) -> None:
    service = TechnologyService(session)
    session.add_all(
        [
            Technology(name="PostgreSQL", canonical="PostgreSQL", category="db"),
            Technology(name="postgres", canonical="PostgreSQL", category="db"),
        ]
    )
    session.commit()
    pg = session.scalars(select(Technology).where(Technology.name == "PostgreSQL")).one()
    assert service.get_or_create("  postgresql ") is pg
    assert service.get_or_create("Postgres") is pg  # alias -> canonical row
    fast = service.get_or_create("  Fast   API ")
    assert (fast.name, fast.canonical) == ("Fast API", "Fast API")
    assert service.get_or_create("fast api") is fast
    with pytest.raises(InvalidDataError):
        service.get_or_create("   ")
    assert [t.canonical for t in service.search("post")] == ["PostgreSQL"]
    assert service.search("api")[0].canonical == "Fast API"


def test_set_experience_technologies(session: Session) -> None:
    resume = _new_resume(session)
    service = ExperienceService(session)
    exp_id = _exp(session, resume.id, "2020-01", "2021-06")
    names = service.set_technologies(exp_id, ["Python", " python ", "", "Docker"])
    assert names == ["Python", "Docker"]
    names = service.set_technologies(exp_id, ["Docker", "Go"])
    assert names == ["Docker", "Go"]
    assert session.scalar(select(func.count()).select_from(Technology)) == 3


def test_project_technologies(session: Session) -> None:
    resume = _new_resume(session)
    service = ProjectService(session)
    proj = service.create(resume.id, ProjectCreate(name="cv-ats", description="Editor de CV"))
    assert service.set_technologies(proj.id, ["FastAPI", "SQLite"]) == ["FastAPI", "SQLite"]


# ------------------------------------------------------------------------ skills etc.


def test_skill_categories_and_skills(session: Session) -> None:
    resume = _new_resume(session)
    TechnologyService(session).get_or_create("Python")
    session.commit()
    service = SkillService(session)
    cat = service.create(resume.id, SkillCategoryCreate(name="Lenguajes"))
    with pytest.raises(ConflictError):
        service.create(resume.id, SkillCategoryCreate(name="lenguajes"))
    skill = service.skills.create(cat.id, SkillCreate(name="python"))
    assert skill.technology_id is not None  # linked to catalog by name
    with pytest.raises(ConflictError):
        service.skills.create(cat.id, SkillCreate(name="Python"))
    with pytest.raises(InvalidDataError):
        service.skills.create(cat.id, SkillCreate(name="Rust", technology_id=999))


def test_language_unique_and_certification_dates(session: Session) -> None:
    resume = _new_resume(session)
    from models.enums import LanguageLevel

    LanguageService(session).create(
        resume.id, LanguageCreate(name="Inglés", level=LanguageLevel.B2)
    )
    with pytest.raises(ConflictError):
        LanguageService(session).create(
            resume.id, LanguageCreate(name="inglés", level=LanguageLevel.C1)
        )
    certs = CertificationService(session)
    cert = certs.create(
        resume.id,
        CertificationCreate(
            name="AWS SAA",
            issuer="Amazon",
            issue_date="2023-05",  # type: ignore[arg-type]
            expiry_date="2026-05",  # type: ignore[arg-type]
        ),
    )
    from schemas import CertificationUpdate

    with pytest.raises(InvalidDataError):
        certs.update(cert.id, CertificationUpdate(expiry_date="2020-01"))  # type: ignore[arg-type]


# ------------------------------------------------------------------------ profiles


def test_change_destination_to_ats_clears_mail_fields(session: Session) -> None:
    resume = _new_resume(session)
    service = ProfileService(session)
    mail = next(p for p in service.list(resume.id) if p.destination == Destination.MAIL)
    service.update(
        mail.id,
        ExportProfileUpdate(include_photo=True, accent_color="#1F6FEB", font_family="Inter"),
    )
    updated = service.update(mail.id, ExportProfileUpdate(destination=Destination.ATS))
    assert updated.destination == Destination.ATS
    assert (updated.include_photo, updated.theme, updated.accent_color) == (False, None, None)
    assert updated.font_family == "Arial"
    back = service.update(mail.id, ExportProfileUpdate(destination=Destination.MAIL))
    assert back.theme == "slate"


def test_profile_validation_and_names(session: Session) -> None:
    resume = _new_resume(session)
    service = ProfileService(session)
    ats = next(p for p in service.list(resume.id) if p.destination == Destination.ATS)
    with pytest.raises(InvalidDataError) as info:
        service.update(ats.id, ExportProfileUpdate(include_photo=True))
    assert info.value.errors[0]["field"] == "include_photo"
    with pytest.raises(ConflictError):
        service.update(ats.id, ExportProfileUpdate(name="Correo"))
    custom = service.create(
        resume.id, ExportProfileCreate(name="Banca", destination=Destination.MAIL, theme="ocean")
    )
    assert len(custom.sections) == 7
    with pytest.raises(ConflictError):
        service.create(resume.id, ExportProfileCreate(name="banca", destination=Destination.ATS))


def test_set_sections(session: Session) -> None:
    resume = _new_resume(session)
    service = ProfileService(session)
    profile = service.list(resume.id)[0]
    order = list(reversed(list(SectionKey)))
    items = [
        ProfileSectionIn(
            section=k,
            visible=k != SectionKey.PROJECTS,
            title_override="Mi experiencia" if k == SectionKey.EXPERIENCE else None,
        )
        for k in order
    ]
    updated = service.set_sections(profile.id, items)
    assert [s.section for s in updated.sections] == order
    projects = next(s for s in updated.sections if s.section == SectionKey.PROJECTS)
    assert projects.visible is False
    with pytest.raises(InvalidDataError):
        service.set_sections(profile.id, items[:6])
    with pytest.raises(InvalidDataError):
        service.set_sections(profile.id, [*items[:6], items[0]])


def test_delete_profile_with_export_job_conflicts(session: Session) -> None:
    resume = _new_resume(session)
    service = ProfileService(session)
    profile = service.list(resume.id)[0]
    session.add(ExportJob(resume_id=resume.id, profile_id=profile.id, format=ExportFormat.PDF))
    session.commit()
    with pytest.raises(ConflictError):
        service.delete(profile.id)
    other = service.list(resume.id)[1]
    service.delete(other.id, resume.id)
    assert len(service.list(resume.id)) == 1


# ------------------------------------------------------------------------ duplicate / snapshot


def _fill(session: Session, resume_id: int) -> None:
    ResumeService(session).update_basics(
        resume_id,
        BasicsUpdate(
            full_name="Ana",
            headline="Backend",
            email="ana@correo.co",
            phone="3001234567",
            city="Bogotá",
            summary="Resumen",
        ),
    )
    ResumeService(session).links.create(
        resume_id, ContactLinkCreate(kind=LinkKind.LINKEDIN, url="https://linkedin.com/in/ana")
    )
    exp_service = ExperienceService(session)
    exp_id = _exp(session, resume_id, "2020-01", None)
    exp_service.achievements.create(exp_id, AchievementCreate(text="Reduje costos 20%"))
    exp_service.set_technologies(exp_id, ["Python", "Docker"])
    skills = SkillService(session)
    cat = skills.create(resume_id, SkillCategoryCreate(name="Lenguajes"))
    skills.skills.create(cat.id, SkillCreate(name="Python"))
    proj = ProjectService(session).create(
        resume_id, ProjectCreate(name="cv-ats", description="Editor")
    )
    ProjectService(session).set_technologies(proj.id, ["FastAPI"])


def _strip_ids(data: object) -> object:
    ignored = {"id", "resume_id", "created_at", "updated_at", "name", "technology_id", "is_default"}
    if isinstance(data, dict):
        return {k: _strip_ids(v) for k, v in data.items() if k not in ignored}
    if isinstance(data, list):
        return [_strip_ids(v) for v in data]
    return data


def test_duplicate_resume_clones_tree(session: Session) -> None:
    resume = _new_resume(session, "General", is_default=True)
    _fill(session, resume.id)
    service = ResumeService(session)
    clone = service.duplicate(resume.id)
    assert clone.name == "General (copia)"
    assert clone.is_default is False
    original, copy = service.get_out(resume.id), service.get_out(clone.id)
    assert _strip_ids(copy.model_dump(mode="json")) == _strip_ids(original.model_dump(mode="json"))
    assert copy.experiences[0].technologies == ["Python", "Docker"]
    assert copy.experiences[0].id != original.experiences[0].id
    assert service.duplicate(resume.id).name == "General (copia 2)"
    with pytest.raises(ConflictError):
        service.duplicate(resume.id, "General")
    assert session.scalar(select(func.count()).select_from(Technology)) == 3  # reused


def test_snapshot_payload_is_resume_out(session: Session) -> None:
    resume = _new_resume(session)
    _fill(session, resume.id)
    service = ResumeService(session)
    snap = service.create_snapshot(resume.id, "v1")
    assert snap.payload == service.get_out(resume.id).model_dump(mode="json")
    assert ResumeOut.model_validate(snap.payload).basics.full_name == "Ana"
    assert [s.id for s in service.list_snapshots(resume.id)] == [snap.id]
    assert service.get_snapshot(snap.id).label == "v1"
    with pytest.raises(NotFoundError):
        service.get_snapshot(999)
