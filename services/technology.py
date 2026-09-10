"""Technology catalog: normalization, get_or_create and autocomplete (spec §4.5 rule 5)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from models import Technology
from services.errors import InvalidDataError


def normalize_name(raw: str) -> str:
    """Trim and collapse inner whitespace."""
    return " ".join(raw.split())


class TechnologyService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _by_canonical(self, canonical: str) -> Technology | None:
        stmt = (
            select(Technology)
            .where(func.lower(Technology.canonical) == canonical.lower())
            .order_by(case((Technology.name == Technology.canonical, 0), else_=1), Technology.id)
        )
        return self.session.scalars(stmt).first()

    def find(self, raw: str) -> Technology | None:
        """Look up by canonical (case-insensitive), then by alias ``name``."""
        name = normalize_name(raw)
        if not name:
            return None
        found = self._by_canonical(name)
        if found is not None:
            return found
        alias = self.session.scalars(select(Technology).where(Technology.name == name)).first()
        if alias is None:
            return None
        return self._by_canonical(alias.canonical) or alias

    def get_or_create(self, raw: str, category: str | None = None) -> Technology:
        """Does not commit: runs inside the caller's transaction."""
        name = normalize_name(raw)
        if not name:
            raise InvalidDataError.single("names", "El nombre de la tecnología está vacío")
        if len(name) > 60:
            raise InvalidDataError.single("names", "Máximo 60 caracteres por tecnología")
        found = self.find(name)
        if found is not None:
            return found
        tech = Technology(name=name, canonical=name, category=category)
        self.session.add(tech)
        self.session.flush()
        return tech

    def resolve_many(self, names: Sequence[str]) -> list[Technology]:
        """get_or_create each name, skipping blanks and duplicates, keeping order."""
        result: list[Technology] = []
        seen: set[int] = set()
        for raw in names:
            if not normalize_name(raw):
                continue
            tech = self.get_or_create(raw)
            if tech.id not in seen:
                seen.add(tech.id)
                result.append(tech)
        return result

    def search(self, query: str, limit: int = 10) -> list[Technology]:
        """Autocomplete: prefix matches first, then substring; one row per canonical."""
        q = normalize_name(query).lower()
        stmt = select(Technology)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    func.lower(Technology.canonical).like(like),
                    func.lower(Technology.name).like(like),
                )
            ).order_by(
                case((func.lower(Technology.canonical).like(f"{q}%"), 0), else_=1),
                func.length(Technology.canonical),
                Technology.canonical,
            )
        else:
            stmt = stmt.order_by(Technology.canonical)
        result: list[Technology] = []
        seen: set[str] = set()
        for tech in self.session.scalars(stmt):
            key = tech.canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(self._by_canonical(tech.canonical) or tech)
            if len(result) >= limit:
                break
        return result
