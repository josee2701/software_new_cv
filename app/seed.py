"""Idempotent seed: technology catalog + example resume (``cv-ats seed``)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seed_data as data
from models import Resume, Technology
from schemas import (
    AchievementCreate,
    BasicsUpdate,
    CertificationCreate,
    ContactLinkCreate,
    EducationCreate,
    ExperienceCreate,
    LanguageCreate,
    ProjectCreate,
    ResumeCreate,
    SkillCategoryCreate,
    SkillCreate,
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

log = logging.getLogger(__name__)


@dataclass
class SeedResult:
    technologies_created: int
    resume_id: int
    resume_created: bool


def seed_technologies(session: Session) -> int:
    """Insert missing catalog rows (by case-insensitive ``name``). Returns rows created."""
    existing = {name.lower() for name in session.scalars(select(Technology.name))}
    created = 0
    rows: list[tuple[str, str, str | None]] = [(name, name, cat) for name, cat in data.TECHNOLOGIES]
    categories = dict(data.TECHNOLOGIES)
    rows += [(alias, canonical, categories.get(canonical)) for alias, canonical in data.ALIASES]
    for name, canonical, category in rows:
        if name.lower() in existing:
            continue
        session.add(Technology(name=name, canonical=canonical, category=category))
        existing.add(name.lower())
        created += 1
    session.commit()
    return created


def seed_example_resume(session: Session, name: str = data.EXAMPLE_RESUME_NAME) -> tuple[int, bool]:
    """Create the example resume if missing. Returns ``(resume_id, created)``."""
    found = session.scalar(select(Resume.id).where(func.lower(Resume.name) == name.lower()))
    if found is not None:
        return found, False

    resumes = ResumeService(session)
    has_default = session.scalar(select(Resume.id).where(Resume.is_default.is_(True)))
    resume = resumes.create(ResumeCreate(name=name, language="es", is_default=has_default is None))
    rid = resume.id
    resumes.update_basics(rid, BasicsUpdate(**data.EXAMPLE_BASICS))
    for link in data.EXAMPLE_LINKS:
        resumes.links.create(rid, ContactLinkCreate.model_validate(link))

    experiences = ExperienceService(session)
    for raw in data.EXAMPLE_EXPERIENCES:
        fields: dict[str, Any] = {
            k: v for k, v in raw.items() if k not in {"achievements", "technologies"}
        }
        exp = experiences.create(rid, ExperienceCreate.model_validate(fields))
        achievements: list[tuple[str, str | None]] = raw["achievements"]  # type: ignore[assignment]
        for text, metric in achievements:
            experiences.achievements.create(
                exp.id, AchievementCreate(text=text, metric_value=metric)
            )
        technologies: list[str] = raw["technologies"]  # type: ignore[assignment]
        experiences.set_technologies(exp.id, technologies)

    for edu in data.EXAMPLE_EDUCATION:
        EducationService(session).create(rid, EducationCreate.model_validate(edu))

    skills = SkillService(session)
    for category, items in data.EXAMPLE_SKILLS:
        cat = skills.create(rid, SkillCategoryCreate(name=category))
        for skill_name, level, years in items:
            skills.skills.create(
                cat.id,
                SkillCreate.model_validate({"name": skill_name, "level": level, "years": years}),
            )

    projects = ProjectService(session)
    for raw_project in data.EXAMPLE_PROJECTS:
        fields = {k: v for k, v in raw_project.items() if k != "technologies"}
        project = projects.create(rid, ProjectCreate.model_validate(fields))
        project_techs: list[str] = raw_project["technologies"]  # type: ignore[assignment]
        projects.set_technologies(project.id, project_techs)

    for cert in data.EXAMPLE_CERTIFICATIONS:
        CertificationService(session).create(rid, CertificationCreate.model_validate(cert))
    for lang_name, level in data.EXAMPLE_LANGUAGES:
        LanguageService(session).create(
            rid, LanguageCreate.model_validate({"name": lang_name, "level": level})
        )
    return rid, True


def run_seed(session: Session) -> SeedResult:
    created = seed_technologies(session)
    resume_id, resume_created = seed_example_resume(session)
    log.info("seed: %s tecnologías nuevas; CV de ejemplo id=%s", created, resume_id)
    return SeedResult(created, resume_id, resume_created)
