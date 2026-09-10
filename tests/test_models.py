"""Model-level integrity: ON DELETE actions, CHECKs, uniques and migrations (spec §4, §14)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from models import (
    Achievement,
    Asset,
    Basics,
    Education,
    Experience,
    ExperienceTechnology,
    ExportJob,
    ExportProfile,
    Language,
    ProfileSection,
    Resume,
    ResumeSnapshot,
    Skill,
    SkillCategory,
    Technology,
    ValidationReport,
)
from models.enums import Destination, ExportFormat, LanguageLevel, SectionKey

ROOT = Path(__file__).resolve().parent.parent


def _resume(session: Session, name: str = "General") -> Resume:
    resume = Resume(name=name)
    resume.basics = Basics(
        full_name="Ana",
        headline="Dev",
        email="a@b.co",
        phone="+573001234567",
        city="Bogotá",
        country="CO",
    )
    session.add(resume)
    session.flush()
    return resume


def _experience(resume: Resume, position: int = 0, **kw: object) -> Experience:
    values: dict[str, object] = {
        "company": "ACME",
        "role": "Dev",
        "start_date": date(2020, 1, 1),
        "end_date": date(2021, 1, 1),
        "is_current": False,
        "position": position,
    }
    values.update(kw)
    exp = Experience(**values)
    resume.experiences.append(exp)
    return exp


def _profile(resume: Resume, name: str = "ATS", **kw: object) -> ExportProfile:
    values: dict[str, object] = {"name": name, "destination": Destination.ATS}
    values.update(kw)
    profile = ExportProfile(**values)
    resume.profiles.append(profile)
    return profile


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ------------------------------------------------------------------------ pragma


def test_foreign_keys_pragma_on(session: Session) -> None:
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


# ------------------------------------------------------------------------ ON DELETE


def test_delete_resume_cascades_whole_tree_sql(session: Session) -> None:
    resume = _resume(session)
    exp = _experience(resume)
    exp.achievements.append(Achievement(text="Hice algo medible", position=0))
    tech = Technology(name="Python", canonical="Python")
    exp.technology_links.append(ExperienceTechnology(technology=tech, position=0))
    cat = SkillCategory(name="Lenguajes", position=0)
    cat.skills.append(Skill(name="Python", position=0))
    resume.skill_categories.append(cat)
    resume.education.append(Education(institution="UN", degree="Ing", position=0))
    resume.languages.append(Language(name="Inglés", level=LanguageLevel.B2, position=0))
    profile = _profile(resume)
    profile.sections.append(ProfileSection(section=SectionKey.SUMMARY, position=0))
    session.flush()
    snapshot = ResumeSnapshot(resume_id=resume.id, label="v1", payload={"a": 1})
    session.add(snapshot)
    session.flush()
    session.add(
        ExportJob(
            resume_id=resume.id,
            profile_id=profile.id,
            format=ExportFormat.PDF,
            snapshot_id=snapshot.id,
        )
    )
    session.add(ValidationReport(resume_id=resume.id, profile_id=profile.id, score=90))
    session.commit()

    session.execute(text("DELETE FROM resume WHERE id = :id"), {"id": resume.id})
    session.commit()
    session.expire_all()

    owned = (
        Basics, Experience, Achievement, ExperienceTechnology, SkillCategory, Skill, Education,
        Language, ExportProfile, ProfileSection, ExportJob, ValidationReport, ResumeSnapshot,
    )  # fmt: skip
    for model in owned:
        assert _count(session, model) == 0, model.__name__
    assert _count(session, Technology) == 1  # the catalog is not owned by the resume


def test_delete_resume_orm_cascade_with_restricted_profile(session: Session) -> None:
    resume = _resume(session)
    profile = _profile(resume)
    _experience(resume)
    session.flush()
    session.add(ExportJob(resume_id=resume.id, profile_id=profile.id, format=ExportFormat.PDF))
    session.commit()
    session.delete(resume)
    session.commit()
    for model in (Basics, ExportJob, ExportProfile, Experience):
        assert _count(session, model) == 0, model.__name__


def test_delete_experience_cascades_achievements_and_links(session: Session) -> None:
    resume = _resume(session)
    exp = _experience(resume)
    exp.achievements.append(Achievement(text="Logro", position=0))
    exp.technology_links.append(
        ExperienceTechnology(technology=Technology(name="Go", canonical="Go"), position=0)
    )
    session.commit()
    session.execute(text("DELETE FROM experience WHERE id = :id"), {"id": exp.id})
    session.commit()
    assert _count(session, Achievement) == 0
    assert _count(session, ExperienceTechnology) == 0
    assert _count(session, Technology) == 1


def test_delete_technology_cascades_m2m_and_sets_skill_null(session: Session) -> None:
    resume = _resume(session)
    tech = Technology(name="Go", canonical="Go")
    exp = _experience(resume)
    exp.technology_links.append(ExperienceTechnology(technology=tech, position=0))
    cat = SkillCategory(name="Lenguajes", position=0)
    cat.skills.append(Skill(name="Go", position=0, technology=tech))
    resume.skill_categories.append(cat)
    session.commit()
    session.execute(text("DELETE FROM technology WHERE id = :id"), {"id": tech.id})
    session.commit()
    session.expire_all()
    assert _count(session, ExperienceTechnology) == 0
    assert cat.skills[0].technology_id is None


def test_delete_asset_sets_photo_null(session: Session) -> None:
    resume = _resume(session)
    asset = Asset(
        filename="x.jpg",
        original_name="yo.jpg",
        mime="image/jpeg",
        width=400,
        height=400,
        size_bytes=1000,
        sha256="a" * 64,
    )
    session.add(asset)
    session.flush()
    assert resume.basics is not None
    resume.basics.photo_asset_id = asset.id
    session.commit()
    session.execute(text("DELETE FROM asset WHERE id = :id"), {"id": asset.id})
    session.commit()
    session.expire_all()
    assert resume.basics.photo_asset_id is None


def test_delete_profile_sets_report_null(session: Session) -> None:
    resume = _resume(session)
    profile = _profile(resume)
    session.flush()
    report = ValidationReport(resume_id=resume.id, profile_id=profile.id, score=80)
    session.add(report)
    session.commit()
    session.execute(text("DELETE FROM export_profile WHERE id = :id"), {"id": profile.id})
    session.commit()
    session.expire_all()
    assert report.profile_id is None


def test_delete_report_and_snapshot_set_export_job_null(session: Session) -> None:
    resume = _resume(session)
    profile = _profile(resume)
    session.flush()
    report = ValidationReport(resume_id=resume.id, profile_id=profile.id, score=80)
    snapshot = ResumeSnapshot(resume_id=resume.id, payload={})
    session.add_all([report, snapshot])
    session.flush()
    job = ExportJob(
        resume_id=resume.id,
        profile_id=profile.id,
        format=ExportFormat.PDF,
        report_id=report.id,
        snapshot_id=snapshot.id,
    )
    session.add(job)
    session.commit()
    session.execute(text("DELETE FROM validation_report WHERE id = :id"), {"id": report.id})
    session.execute(text("DELETE FROM resume_snapshot WHERE id = :id"), {"id": snapshot.id})
    session.commit()
    session.expire_all()
    assert (job.report_id, job.snapshot_id) == (None, None)


def test_delete_profile_with_export_job_is_restricted(session: Session) -> None:
    resume = _resume(session)
    profile = _profile(resume)
    session.flush()
    session.add(ExportJob(resume_id=resume.id, profile_id=profile.id, format=ExportFormat.PDF))
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(text("DELETE FROM export_profile WHERE id = :id"), {"id": profile.id})
    session.rollback()


# ------------------------------------------------------------------------ CHECKs


@pytest.mark.parametrize(("is_current", "end_date"), [(True, date(2021, 1, 1)), (False, None)])
def test_check_is_current_end_date(
    session: Session, is_current: bool, end_date: date | None
) -> None:
    resume = _resume(session)
    _experience(resume, is_current=is_current, end_date=end_date)
    with pytest.raises(IntegrityError, match="current_end_date"):
        session.flush()


def test_check_current_experience_ok(session: Session) -> None:
    resume = _resume(session)
    _experience(resume, is_current=True, end_date=None)
    session.flush()


def test_check_experience_end_before_start(session: Session) -> None:
    resume = _resume(session)
    _experience(resume, start_date=date(2022, 1, 1), end_date=date(2021, 1, 1))
    with pytest.raises(IntegrityError, match="end_after_start"):
        session.flush()


@pytest.mark.parametrize(
    ("kwargs", "constraint"),
    [
        ({"include_photo": True}, "ats_no_photo"),
        ({"theme": "slate"}, "theme"),
        ({"accent_color": "#123456"}, "accent_color"),
        ({"font_family": "Comic Sans"}, "ats_font"),
        ({"max_pages": 4}, "max_pages"),
        ({"date_format": "DD/MM/YYYY"}, "date_format"),
    ],
)
def test_check_ats_profile_rules(
    session: Session, kwargs: dict[str, object], constraint: str
) -> None:
    resume = _resume(session)
    _profile(resume, **kwargs)
    with pytest.raises(IntegrityError, match=constraint):
        session.flush()


def test_check_mail_profile_requires_theme(session: Session) -> None:
    resume = _resume(session)
    _profile(resume, name="m1", destination=Destination.MAIL)
    with pytest.raises(IntegrityError, match="theme"):
        session.flush()


def test_check_mail_profile_accent_color_format(session: Session) -> None:
    resume = _resume(session)
    _profile(resume, name="m2", destination=Destination.MAIL, theme="slate", accent_color="#12345G")
    with pytest.raises(IntegrityError, match="accent_color"):
        session.flush()


def test_check_mail_profile_valid(session: Session) -> None:
    resume = _resume(session)
    _profile(
        resume,
        name="m3",
        destination=Destination.MAIL,
        theme="slate",
        accent_color="#1F6FEB",
        include_photo=True,
        font_family="Inter",
    )
    session.flush()


def test_check_enum_values(session: Session) -> None:
    resume = _resume(session)
    session.commit()
    with pytest.raises(IntegrityError, match="show_in"):
        session.execute(
            text(
                "INSERT INTO education (resume_id, institution, degree, show_in, position) "
                "VALUES (:r, 'UN', 'Ing', 'nope', 0)"
            ),
            {"r": resume.id},
        )
    session.rollback()


@pytest.mark.parametrize(
    ("sql", "constraint"),
    [
        ("UPDATE basics SET summary = :long WHERE resume_id = :r", "summary_length"),
        ("UPDATE resume SET language = 'fr' WHERE id = :r", "language"),
        (
            "INSERT INTO asset (filename, original_name, mime, width, height, size_bytes, sha256)"
            " VALUES ('a', 'a', 'image/gif', 1, 1, 1, :h)",
            "mime",
        ),
        (
            "INSERT INTO asset (filename, original_name, mime, width, height, size_bytes, sha256)"
            " VALUES ('a', 'a', 'image/png', 1, 1, 5000001, :h)",
            "size_bytes",
        ),
        ("INSERT INTO validation_report (resume_id, score) VALUES (:r, 101)", "score"),
        (
            "INSERT INTO skill_category (resume_id, name, position) VALUES (:r, 'c', 0)",
            None,
        ),
    ],
)
def test_check_misc(session: Session, sql: str, constraint: str | None) -> None:
    resume = _resume(session)
    session.commit()
    params = {"r": resume.id, "long": "x" * 1201, "h": "b" * 64}
    if constraint is None:  # control case: valid statement passes
        session.execute(text(sql), params)
        return
    with pytest.raises(IntegrityError, match=constraint):
        session.execute(text(sql), params)
    session.rollback()


def test_check_skill_years_range(session: Session) -> None:
    resume = _resume(session)
    cat = SkillCategory(name="X", position=0)
    cat.skills.append(Skill(name="Python", position=0, years=51))
    resume.skill_categories.append(cat)
    with pytest.raises(IntegrityError, match="years"):
        session.flush()


# ------------------------------------------------------------------------ uniques


def test_partial_unique_index_single_default_resume(session: Session) -> None:
    session.add_all([Resume(name="A", is_default=True), Resume(name="B"), Resume(name="C")])
    session.flush()  # many non-default rows are allowed
    session.add(Resume(name="D", is_default=True))
    with pytest.raises(IntegrityError, match="is_default"):
        session.flush()


def test_partial_index_is_declared_with_where(engine: Engine) -> None:
    with engine.connect() as conn:
        sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'uq_resume_single_default'")
        ).scalar_one()
    assert "UNIQUE" in sql.upper() and "WHERE is_default = 1" in sql


def test_unique_resume_name(session: Session) -> None:
    session.add(Resume(name="A"))
    session.flush()
    session.add(Resume(name="A"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_basics_per_resume(session: Session) -> None:
    resume = _resume(session)
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO basics (resume_id, full_name, headline, email, phone, city, country)"
                " VALUES (:r, '', '', '', '', '', 'CO')"
            ),
            {"r": resume.id},
        )
    session.rollback()


def test_unique_position_per_parent(session: Session) -> None:
    resume = _resume(session)
    _experience(resume, position=0)
    _experience(resume, position=0)
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_technology_name_nocase(session: Session) -> None:
    session.add(Technology(name="PostgreSQL", canonical="PostgreSQL"))
    session.flush()
    session.add(Technology(name="postgresql", canonical="PostgreSQL"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_skill_category_name(session: Session) -> None:
    resume = _resume(session)
    resume.skill_categories.append(SkillCategory(name="X", position=0))
    resume.skill_categories.append(SkillCategory(name="X", position=1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_language_name(session: Session) -> None:
    resume = _resume(session)
    resume.languages.append(Language(name="Inglés", level=LanguageLevel.B2, position=0))
    resume.languages.append(Language(name="Inglés", level=LanguageLevel.C1, position=1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_profile_section(session: Session) -> None:
    resume = _resume(session)
    profile = _profile(resume)
    profile.sections.append(ProfileSection(section=SectionKey.SKILLS, position=0))
    profile.sections.append(ProfileSection(section=SectionKey.SKILLS, position=1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_profile_name_per_resume(session: Session) -> None:
    resume = _resume(session)
    _profile(resume, name="P")
    _profile(resume, name="P")
    with pytest.raises(IntegrityError):
        session.flush()


def test_every_foreign_key_is_indexed_and_has_ondelete(engine: Engine) -> None:
    insp = inspect(engine)
    for table in insp.get_table_names():
        indexed = {next(iter(ix["column_names"])) for ix in insp.get_indexes(table)}
        indexed |= {next(iter(uq["column_names"])) for uq in insp.get_unique_constraints(table)}
        pk = insp.get_pk_constraint(table)["constrained_columns"]
        if pk:
            indexed.add(pk[0])
        for fk in insp.get_foreign_keys(table):
            col = fk["constrained_columns"][0]
            assert col in indexed, f"{table}.{col} sin índice"
            assert fk["options"].get("ondelete"), f"{table}.{col} sin ON DELETE"


# ------------------------------------------------------------------------ migrations


def test_migrations_match_models(tmp_path: Path) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migrated.db'}")
    command.upgrade(cfg, "head")
    command.check(cfg)  # raises if autogenerate detects any difference
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
