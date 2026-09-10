"""Simple resume sections: education, projects, certifications, languages, skills."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models import (
    Certification,
    Education,
    Language,
    Project,
    ProjectTechnology,
    Resume,
    Skill,
    SkillCategory,
    Technology,
)
from schemas import (
    CertificationCreate,
    EducationCreate,
    LanguageCreate,
    ProjectCreate,
    SkillCategoryCreate,
    SkillCreate,
)
from services.base import ChildService
from services.errors import InvalidDataError
from services.technology import TechnologyService


class EducationService(ChildService[Education]):
    model = Education
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = EducationCreate
    label = "la educación"
    parent_label = "el CV"


class CertificationService(ChildService[Certification]):
    model = Certification
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = CertificationCreate
    label = "la certificación"
    parent_label = "el CV"


class LanguageService(ChildService[Language]):
    model = Language
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = LanguageCreate
    label = "el idioma"
    parent_label = "el CV"
    unique_fields = ("name",)
    unique_message = "Ese idioma ya está en el CV"


class ProjectService(ChildService[Project]):
    model = Project
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = ProjectCreate
    label = "el proyecto"
    parent_label = "el CV"

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.technologies = TechnologyService(session)

    def set_technologies(self, project_id: int, names: list[str]) -> list[str]:
        with self._write():
            project = self.get(project_id)
            techs = self.technologies.resolve_many(names)
            project.technology_links.clear()
            self.session.flush()
            project.technology_links.extend(
                ProjectTechnology(technology=t, position=i) for i, t in enumerate(techs)
            )
            self.session.flush()
            result = project.technologies
        return result


class SkillItemService(ChildService[Skill]):
    model = Skill
    parent_model = SkillCategory
    parent_fk = "category_id"
    create_schema = SkillCreate
    label = "la habilidad"
    parent_label = "la categoría"
    unique_fields = ("name",)
    unique_message = "Esa habilidad ya existe en la categoría"

    def _check_refs(self, values: dict[str, Any]) -> None:
        tech_id = values.get("technology_id")
        if tech_id is not None and self.session.get(Technology, tech_id) is None:
            raise InvalidDataError.single("technology_id", "La tecnología no existe")

    def _after_write(self, item: Skill) -> None:
        # Link to the catalog when the name matches a known technology (lookup only).
        if item.technology_id is None:
            tech = TechnologyService(self.session).find(item.name)
            if tech is not None:
                item.technology_id = tech.id
                self.session.flush()


class SkillService(ChildService[SkillCategory]):
    """Skill aggregate: categories (this class) and their skills (``self.skills``)."""

    model = SkillCategory
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = SkillCategoryCreate
    label = "la categoría"
    parent_label = "el CV"
    unique_fields = ("name",)
    unique_message = "Ya existe una categoría con ese nombre"

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.skills = SkillItemService(session)
