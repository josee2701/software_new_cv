"""Resume aggregate: resume, basics, contact links, duplicate and snapshots."""

from __future__ import annotations

import builtins
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, inspect, select, update
from sqlalchemy.orm import Session

from models import (
    Achievement,
    Asset,
    Basics,
    Certification,
    ContactLink,
    Education,
    Experience,
    ExperienceTechnology,
    ExportJob,
    ExportProfile,
    Language,
    ProfileSection,
    Project,
    ProjectTechnology,
    Resume,
    ResumeSnapshot,
    Skill,
    SkillCategory,
    Technology,
)
from models.base import Base
from models.enums import LinkKind
from schemas import (
    BasicsUpdate,
    ContactLinkCreate,
    ExportProfileOut,
    ResumeCreate,
    ResumeOut,
    ResumeUpdate,
)
from services.base import ChildService, TransactionalService
from services.errors import ConflictError, InvalidDataError, NotFoundError
from services.profile import default_profiles
from services.technology import TechnologyService

_SKIP_COLUMNS = {"id", "created_at", "updated_at"}


def empty_basics() -> Basics:
    """Placeholder basics for a new resume: NOT NULL columns get empty strings."""
    return Basics(full_name="", headline="", email="", phone="", city="", country="CO")


_CONTENT_RELATIONS = (
    "links",
    "experiences",
    "education",
    "skill_categories",
    "projects",
    "certifications",
    "languages",
)


def _column_values(model: type[Base], source: BaseModel) -> dict[str, Any]:
    """Column fields of ``model`` present in ``source`` (without id/timestamps)."""
    names = {attr.key for attr in inspect(model).column_attrs} - _SKIP_COLUMNS
    return {k: v for k, v in source.model_dump().items() if k in names}


def _columns(model: type[Base], source: BaseModel, **extra: Any) -> Any:
    """Build a new ``model`` instance from the column fields present in ``source``."""
    data = _column_values(model, source)
    data.update(extra)
    return model(**data)


def _new_profile(source: ExportProfileOut) -> ExportProfile:
    profile: ExportProfile = _columns(ExportProfile, source, resume_id=None)
    profile.sections = [_columns(ProfileSection, s) for s in source.sections]
    return profile


class LinkService(ChildService[ContactLink]):
    model = ContactLink
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = ContactLinkCreate
    label = "el enlace"
    parent_label = "el CV"

    def _check_unique(self, parent_id: int, values: dict[str, Any], exclude_id: int | None) -> None:
        kind = values.get("kind")
        if kind is None or kind == LinkKind.OTHER:
            return
        stmt = select(ContactLink.id).where(
            ContactLink.resume_id == parent_id, ContactLink.kind == kind
        )
        if exclude_id is not None:
            stmt = stmt.where(ContactLink.id != exclude_id)
        if self.session.scalar(stmt) is not None:
            raise ConflictError(f"Ya existe un enlace de tipo {LinkKind(kind).value}")


class ResumeService(TransactionalService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.links = LinkService(session)

    # ------------------------------------------------------------------ reads

    def list(self) -> list[Resume]:
        stmt = select(Resume).order_by(Resume.is_default.desc(), Resume.name)
        return list(self.session.scalars(stmt))

    def get(self, resume_id: int) -> Resume:
        resume = self.session.get(Resume, resume_id)
        if resume is None:
            raise NotFoundError(f"No existe el CV con id {resume_id}")
        return resume

    def get_out(self, resume_id: int) -> ResumeOut:
        """Full tree (``ResumeOut``): the contract for render, validator, snapshot, export."""
        self.session.expire_all()
        return ResumeOut.model_validate(self.get(resume_id))

    # ------------------------------------------------------------------ writes

    def _check_name(self, name: str, exclude_id: int | None) -> None:
        stmt = select(Resume.id).where(func.lower(Resume.name) == name.lower())
        if exclude_id is not None:
            stmt = stmt.where(Resume.id != exclude_id)
        if self.session.scalar(stmt) is not None:
            raise ConflictError("Ya existe un CV con ese nombre")

    def _clear_default(self, except_id: int | None) -> None:
        stmt = update(Resume).where(Resume.is_default.is_(True))
        if except_id is not None:
            stmt = stmt.where(Resume.id != except_id)
        self.session.execute(stmt.values(is_default=False))

    def create(self, data: ResumeCreate) -> Resume:
        """Creates the resume + empty basics + "Plataforma"/"Correo" profiles (7 sections each)."""
        with self._write():
            self._check_name(data.name, None)
            if data.is_default:
                self._clear_default(None)
            resume = Resume(**data.model_dump())
            resume.basics = empty_basics()
            resume.profiles = default_profiles()
            self.session.add(resume)
            self.session.flush()
        return resume

    def update(self, resume_id: int, patch: ResumeUpdate) -> Resume:
        with self._write():
            resume = self.get(resume_id)
            changes = patch.model_dump(exclude_unset=True)
            for required in ("name", "language", "is_default"):
                if required in changes and changes[required] is None:
                    raise InvalidDataError.single(required, "Campo obligatorio")
            if "name" in changes:
                self._check_name(changes["name"], resume_id)
            if changes.get("is_default"):
                self._clear_default(resume_id)
            for name, value in changes.items():
                setattr(resume, name, value)
            self.session.flush()
        return resume

    def delete(self, resume_id: int) -> None:
        with self._write():
            self.session.delete(self.get(resume_id))

    def _unique_copy_name(self, base: str) -> str:
        candidate = f"{base} (copia)"[:120]
        n = 2
        while self.session.scalar(select(Resume.id).where(Resume.name == candidate)) is not None:
            candidate = f"{base} (copia {n})"[:120]
            n += 1
        return candidate

    def duplicate(self, resume_id: int, name: str | None = None) -> Resume:
        """Clone the whole tree (new name, never default). The photo asset is shared."""
        source = self.get_out(resume_id)
        with self._write():
            if name:
                self._check_name(name, None)
            new_name = name or self._unique_copy_name(source.name)
            clone = Resume(
                name=new_name, language=source.language, is_default=False, notes=source.notes
            )
            with self.session.no_autoflush:
                self._populate(clone, source)
            self.session.add(clone)
            self.session.flush()
        return clone

    def _populate(self, target: Resume, src: ResumeOut) -> None:
        target.basics = _columns(Basics, src.basics)
        self._populate_content(target, src)
        target.profiles = [_new_profile(p) for p in src.profiles]

    def _populate_content(self, target: Resume, src: ResumeOut) -> None:
        """Add links, experiences, education, skills, projects, certifications, languages."""
        techs = TechnologyService(self.session)
        for link in src.links:
            target.links.append(_columns(ContactLink, link))
        for exp_out in src.experiences:
            exp: Experience = _columns(Experience, exp_out)
            exp.achievements = [_columns(Achievement, a) for a in exp_out.achievements]
            exp.technology_links = [
                ExperienceTechnology(technology=techs.get_or_create(n), position=i)
                for i, n in enumerate(exp_out.technologies)
            ]
            target.experiences.append(exp)
        for edu in src.education:
            target.education.append(_columns(Education, edu))
        for cat_out in src.skill_categories:
            cat: SkillCategory = _columns(SkillCategory, cat_out)
            skills: list[Skill] = [_columns(Skill, s) for s in cat_out.skills]
            for skill in skills:
                if skill.technology_id is not None and (
                    self.session.get(Technology, skill.technology_id) is None
                ):
                    skill.technology_id = None
            cat.skills = skills
            target.skill_categories.append(cat)
        for proj_out in src.projects:
            proj: Project = _columns(Project, proj_out)
            proj.technology_links = [
                ProjectTechnology(technology=techs.get_or_create(n), position=i)
                for i, n in enumerate(proj_out.technologies)
            ]
            target.projects.append(proj)
        for cert in src.certifications:
            target.certifications.append(_columns(Certification, cert))
        for lang in src.languages:
            target.languages.append(_columns(Language, lang))

    # ------------------------------------------------------------------ restore

    def restore_snapshot(self, snapshot_id: int) -> Resume:
        """Rebuild the resume from a snapshot payload in one transaction.

        Content lists are recreated (new ids); basics and matching profiles (by id) are
        updated in place so export jobs keep their profile. ``is_default`` is not touched.
        """
        snapshot = self.get_snapshot(snapshot_id)
        src = ResumeOut.model_validate(snapshot.payload)
        with self._write():
            resume = self.get(snapshot.resume_id)
            if src.name.lower() != resume.name.lower():
                taken = self.session.scalar(
                    select(Resume.id).where(
                        func.lower(Resume.name) == src.name.lower(), Resume.id != resume.id
                    )
                )
                if taken is None:
                    resume.name = src.name
            resume.language = src.language
            resume.notes = src.notes
            for relation in _CONTENT_RELATIONS:
                getattr(resume, relation).clear()
            self.session.flush()
            self._restore_basics(resume, src)
            self._restore_profiles(resume, src)
            with self.session.no_autoflush:
                self._populate_content(resume, src)
            self.session.flush()
        return resume

    def _restore_basics(self, resume: Resume, src: ResumeOut) -> None:
        if resume.basics is None:
            resume.basics = empty_basics()
        values = _column_values(Basics, src.basics)
        asset_id = values.get("photo_asset_id")
        if asset_id is not None and self.session.get(Asset, asset_id) is None:
            values["photo_asset_id"] = None
        for name, value in values.items():
            setattr(resume.basics, name, value)

    def _restore_profiles(self, resume: Resume, src: ResumeOut) -> None:
        wanted = {p.id for p in src.profiles}
        for profile in list(resume.profiles):
            if profile.id in wanted:
                continue
            used = self.session.scalar(
                select(ExportJob.id).where(ExportJob.profile_id == profile.id).limit(1)
            )
            if used is None:  # profiles with export jobs are kept (RESTRICT)
                resume.profiles.remove(profile)
        self.session.flush()
        current = {p.id: p for p in resume.profiles}
        for prof_out in src.profiles:
            existing = current.get(prof_out.id)
            if existing is None:
                resume.profiles.append(_new_profile(prof_out))
                continue
            for name, value in _column_values(ExportProfile, prof_out).items():
                if name != "resume_id":
                    setattr(existing, name, value)
            existing.sections.clear()
            self.session.flush()
            existing.sections = [_columns(ProfileSection, s) for s in prof_out.sections]
        self.session.flush()

    # ------------------------------------------------------------------ basics

    def get_basics(self, resume_id: int) -> Basics:
        resume = self.get(resume_id)
        if resume.basics is None:  # defensive: every resume is created with basics
            with self._write():
                resume.basics = empty_basics()
                self.session.flush()
        assert resume.basics is not None
        return resume.basics

    def update_basics(self, resume_id: int, patch: BasicsUpdate) -> Basics:
        """Merge only the fields sent (``exclude_unset``)."""
        basics = self.get_basics(resume_id)
        with self._write():
            changes = patch.model_dump(exclude_unset=True)
            for required in ("full_name", "headline", "email", "phone", "city", "country"):
                if required in changes and changes[required] is None:
                    raise InvalidDataError.single(required, "Campo obligatorio")
            asset_id = changes.get("photo_asset_id")
            if asset_id is not None and self.session.get(Asset, asset_id) is None:
                raise InvalidDataError.single("photo_asset_id", "La foto no existe")
            for name, value in changes.items():
                setattr(basics, name, value)
            self.session.flush()
        return basics

    # ------------------------------------------------------------------ snapshots

    def create_snapshot(self, resume_id: int, label: str | None = None) -> ResumeSnapshot:
        payload = self.get_out(resume_id).model_dump(mode="json")
        with self._write():
            snapshot = ResumeSnapshot(resume_id=resume_id, label=label, payload=payload)
            self.session.add(snapshot)
            self.session.flush()
        return snapshot

    def list_snapshots(self, resume_id: int) -> builtins.list[ResumeSnapshot]:
        self.get(resume_id)
        stmt = (
            select(ResumeSnapshot)
            .where(ResumeSnapshot.resume_id == resume_id)
            .order_by(ResumeSnapshot.id.desc())
        )
        return list(self.session.scalars(stmt))

    def get_snapshot(self, snapshot_id: int) -> ResumeSnapshot:
        snapshot = self.session.get(ResumeSnapshot, snapshot_id)
        if snapshot is None:
            raise NotFoundError(f"No existe la versión con id {snapshot_id}")
        return snapshot
