"""Experience aggregate: experiences, achievements and technologies."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from sqlalchemy.orm import Session

from models import Achievement, Experience, ExperienceTechnology, Resume
from schemas import AchievementCreate, ExperienceCreate
from services.base import ChildService, apply_order
from services.technology import TechnologyService


def _is_reverse_chronological(items: list[Experience]) -> bool:
    return all(a.start_date >= b.start_date for a, b in pairwise(items))


class AchievementService(ChildService[Achievement]):
    model = Achievement
    parent_model = Experience
    parent_fk = "experience_id"
    create_schema = AchievementCreate
    label = "el logro"
    parent_label = "la experiencia"


class ExperienceService(ChildService[Experience]):
    """New or edited experiences keep reverse-chronological order unless the user
    has already reordered them manually (spec §8.1)."""

    model = Experience
    parent_model = Resume
    parent_fk = "resume_id"
    create_schema = ExperienceCreate
    label = "la experiencia"
    parent_label = "el CV"

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.achievements = AchievementService(session)
        self.technologies = TechnologyService(session)

    def _prepare_update(self, item: Experience, changes: dict[str, Any]) -> dict[str, Any]:
        if changes.get("is_current") is True and "end_date" not in changes:
            changes["end_date"] = None
        return changes

    def _after_write(self, item: Experience) -> None:
        items = self.list(item.resume_id)
        others = [e for e in items if e.id != item.id]
        if not _is_reverse_chronological(others):
            return
        ordered = sorted(items, key=lambda e: (e.start_date, e.is_current), reverse=True)
        if [e.id for e in ordered] != [e.id for e in items]:
            apply_order(self.session, ordered)

    def set_technologies(self, experience_id: int, names: list[str]) -> list[str]:
        with self._write():
            exp = self.get(experience_id)
            techs = self.technologies.resolve_many(names)
            exp.technology_links.clear()
            self.session.flush()
            exp.technology_links.extend(
                ExperienceTechnology(technology=t, position=i) for i, t in enumerate(techs)
            )
            self.session.flush()
            result = exp.technologies
        return result
