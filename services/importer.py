"""Import service: preview (no writes) and apply (one transaction) — spec §11."""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from importer import ImportFormatError, parse_document
from models import (
    Achievement,
    Certification,
    ContactLink,
    Education,
    Experience,
    ExperienceTechnology,
    Language,
    Project,
    ProjectTechnology,
    Resume,
    Skill,
    SkillCategory,
)
from models.enums import LinkKind
from schemas import (
    AchievementCreate,
    BasicsUpdate,
    CertificationCreate,
    ContactLinkCreate,
    EducationCreate,
    ExperienceCreate,
    LanguageCreate,
    ProjectCreate,
    SkillCategoryCreate,
    SkillCreate,
)
from schemas.errors import to_field_errors
from schemas.importer import ImportApplyResult, ImportPreview, SkippedItem
from services.base import TransactionalService
from services.errors import InvalidDataError
from services.resume import ResumeService
from services.technology import TechnologyService

Mode = Literal["replace", "append"]
MAX_UPLOAD_BYTES = 10_000_000
_CONTENT = ("links", "experiences", "education", "skill_categories", "projects",
            "certifications", "languages")  # fmt: skip
_BASICS_FIELDS = ("full_name", "headline", "email", "city", "region", "summary")


class ImportService(TransactionalService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ------------------------------------------------------------------ preview

    def preview(self, resume_id: int, data: bytes, filename: str | None = None) -> ImportPreview:
        """Parse the file into an editable preview. Never writes."""
        ResumeService(self.session).get(resume_id)  # 404
        if not data:
            raise InvalidDataError.single("file", "El archivo está vacío")
        if len(data) > MAX_UPLOAD_BYTES:
            raise InvalidDataError.single("file", "El archivo supera 10 MB")
        try:
            return parse_document(data, filename)
        except ImportFormatError as exc:
            raise InvalidDataError.single("file", str(exc)) from exc

    # ------------------------------------------------------------------ apply

    def apply(
        self, resume_id: int, preview: ImportPreview, mode: Mode = "replace"
    ) -> ImportApplyResult:
        """Write the (edited) preview. ``replace`` empties the content lists first;
        ``append`` adds after the existing items. Basics fields are overwritten only when the
        preview has a value. Invalid items are skipped and reported; the rest is atomic."""
        skipped: list[SkippedItem] = []
        created: Counter[str] = Counter()
        resumes = ResumeService(self.session)
        resume = resumes.get(resume_id)
        plan = _Plan.build(preview, skipped)
        with self._write():
            if mode == "replace":
                for relation in _CONTENT:
                    getattr(resume, relation).clear()
                self.session.flush()
            self._apply_basics(resume, plan.basics)
            self._write_content(resume, plan, mode, created, skipped)
            self.session.flush()
        return ImportApplyResult(
            resume=resumes.get_out(resume_id), created=dict(created), skipped=skipped
        )

    def _apply_basics(self, resume: Resume, patch: dict[str, Any]) -> None:
        basics = ResumeService(self.session).get_basics(resume.id)
        for name, value in patch.items():
            setattr(basics, name, value)

    def _write_content(
        self,
        resume: Resume,
        plan: _Plan,
        mode: Mode,
        created: Counter[str],
        skipped: list[SkippedItem],
    ) -> None:
        techs = TechnologyService(self.session)
        kinds: set[LinkKind] = {link.kind for link in resume.links}
        for link in plan.links:
            if link.kind is not LinkKind.OTHER and link.kind in kinds:
                skipped.append(SkippedItem(path=f"links.{link.kind.value}", reason="Ya existe"))
                continue
            kinds.add(link.kind)
            resume.links.append(ContactLink(**link.model_dump(), position=len(resume.links)))
            created["links"] += 1
        for exp_data, achievements, tech_names in plan.experiences:
            exp = Experience(**exp_data.model_dump(), position=len(resume.experiences))
            exp.achievements = [
                Achievement(**a.model_dump(), position=i) for i, a in enumerate(achievements)
            ]
            exp.technology_links = [
                ExperienceTechnology(technology=t, position=i)
                for i, t in enumerate(techs.resolve_many(tech_names))
            ]
            resume.experiences.append(exp)
            created["experiences"] += 1
        for edu in plan.education:
            resume.education.append(Education(**edu.model_dump(), position=len(resume.education)))
            created["education"] += 1
        categories = {c.name.lower(): c for c in resume.skill_categories}
        for cat_data, skills in plan.skill_categories:
            category = categories.get(cat_data.name.lower())
            if category is None:
                category = SkillCategory(name=cat_data.name, position=len(resume.skill_categories))
                resume.skill_categories.append(category)
                categories[cat_data.name.lower()] = category
                created["skill_categories"] += 1
            names = {s.name.lower() for s in category.skills}
            for skill in skills:
                if skill.name.lower() in names:
                    continue
                names.add(skill.name.lower())
                tech = techs.find(skill.name)
                category.skills.append(Skill(
                    **skill.model_dump(exclude={"technology_id"}),
                    technology_id=tech.id if tech else None,
                    position=len(category.skills),
                ))  # fmt: skip
                created["skills"] += 1
        for proj_data, tech_names in plan.projects:
            project = Project(**proj_data.model_dump(), position=len(resume.projects))
            project.technology_links = [
                ProjectTechnology(technology=t, position=i)
                for i, t in enumerate(techs.resolve_many(tech_names))
            ]
            resume.projects.append(project)
            created["projects"] += 1
        for cert in plan.certifications:
            resume.certifications.append(
                Certification(**cert.model_dump(), position=len(resume.certifications))
            )
            created["certifications"] += 1
        existing_langs = {lang.name.lower() for lang in resume.languages}
        for lang in plan.languages:
            if lang.name.lower() in existing_langs:
                skipped.append(SkippedItem(path=f"languages.{lang.name}", reason="Ya existe"))
                continue
            existing_langs.add(lang.name.lower())
            resume.languages.append(Language(**lang.model_dump(), position=len(resume.languages)))
            created["languages"] += 1


def _validate[S: BaseModel](
    schema: type[S], data: dict[str, Any], path: str, skipped: list[SkippedItem]
) -> S | None:
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        reasons = "; ".join(
            f"{e['field']}: {e['msg']}" if e["field"] else e["msg"]
            for e in to_field_errors(exc.errors())
        )
        skipped.append(SkippedItem(path=path, reason=reasons))
        return None


class _Plan:
    """Preview → validated Create schemas (pure; invalid items are reported and dropped)."""

    def __init__(self) -> None:
        self.basics: dict[str, Any] = {}
        self.links: list[ContactLinkCreate] = []
        self.experiences: list[tuple[ExperienceCreate, list[AchievementCreate], list[str]]] = []
        self.education: list[EducationCreate] = []
        self.skill_categories: list[tuple[SkillCategoryCreate, list[SkillCreate]]] = []
        self.projects: list[tuple[ProjectCreate, list[str]]] = []
        self.certifications: list[CertificationCreate] = []
        self.languages: list[LanguageCreate] = []

    @classmethod
    def build(cls, p: ImportPreview, skipped: list[SkippedItem]) -> _Plan:
        plan = cls()
        b = p.basics
        country = b.country.value
        values: dict[str, Any] = {f: getattr(b, f).value for f in _BASICS_FIELDS}
        if country:
            values["country"] = country
        if b.phone.value:
            values["phone"] = b.phone.value
        for name, value in values.items():
            if value in (None, ""):
                continue
            data = {name: value}
            if name == "phone" and country:
                data["country"] = country
            if (ok := _validate(BasicsUpdate, data, f"basics.{name}", skipped)) is not None:
                plan.basics[name] = getattr(ok, name)
        for i, link in enumerate(p.links):
            data = {"kind": link.kind, "url": link.url}
            if (created := _validate(ContactLinkCreate, data, f"links.{i}", skipped)) is not None:
                plan.links.append(created)
        for i, e in enumerate(p.experiences):
            current = e.is_current.value
            if e.start_date.value is None:
                skipped.append(
                    SkippedItem(path=f"experiences.{i}", reason="Falta la fecha de inicio")
                )
                continue
            exp = _validate(ExperienceCreate, {
                "company": e.company.value, "role": e.role.value, "city": e.city.value,
                "country": e.country.value, "remote": e.remote.value,
                "start_date": e.start_date.value,
                "end_date": None if current else e.end_date.value, "is_current": current,
                "description": (e.description.value or "")[:400] or None,
            }, f"experiences.{i}", skipped)  # fmt: skip
            if exp is None:
                continue
            achievements = [
                a for j, item in enumerate(e.achievements)
                if (a := _validate(AchievementCreate, {"text": item.text[:300]},
                                   f"experiences.{i}.achievements.{j}", skipped)) is not None
            ]  # fmt: skip
            plan.experiences.append((exp, achievements, e.technologies.value))
        for i, ed in enumerate(p.education):
            edu = _validate(EducationCreate, {
                "institution": ed.institution.value, "degree": ed.degree.value,
                "level": ed.level.value, "field": ed.field.value, "city": ed.city.value,
                "start_date": ed.start_date.value,
                "end_date": None if ed.in_progress.value else ed.end_date.value,
                "in_progress": ed.in_progress.value, "gpa": ed.gpa.value,
            }, f"education.{i}", skipped)  # fmt: skip
            if edu is not None:
                plan.education.append(edu)
        for i, c in enumerate(p.skill_categories):
            cat = _validate(
                SkillCategoryCreate, {"name": c.name.value}, f"skill_categories.{i}", skipped
            )
            if cat is None:
                continue
            skills = [
                s for j, item in enumerate(c.skills)
                if (s := _validate(SkillCreate, {"name": item.text},
                                   f"skill_categories.{i}.skills.{j}", skipped)) is not None
            ]  # fmt: skip
            plan.skill_categories.append((cat, skills))
        for i, pr in enumerate(p.projects):
            proj = _validate(ProjectCreate, {
                "name": pr.name.value, "role": pr.role.value,
                "description": pr.description.value or pr.name.value, "url": pr.url.value,
                "start_date": pr.start_date.value, "end_date": pr.end_date.value,
            }, f"projects.{i}", skipped)  # fmt: skip
            if proj is not None:
                plan.projects.append((proj, pr.technologies.value))
        for i, ce in enumerate(p.certifications):
            cert = _validate(CertificationCreate, {
                "name": ce.name.value, "issuer": ce.issuer.value,
                "issue_date": ce.issue_date.value, "expiry_date": ce.expiry_date.value,
                "credential_id": ce.credential_id.value, "url": ce.url.value,
            }, f"certifications.{i}", skipped)  # fmt: skip
            if cert is not None:
                plan.certifications.append(cert)
        for i, la in enumerate(p.languages):
            data = {"name": la.name.value, "level": la.level.value}
            if (lang := _validate(LanguageCreate, data, f"languages.{i}", skipped)) is not None:
                plan.languages.append(lang)
        return plan
