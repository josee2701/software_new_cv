"""Export profiles and their section order/visibility."""

from __future__ import annotations

import builtins
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import ExportProfile, ProfileSection, Resume
from models.enums import Destination, SectionKey
from schemas import ExportProfileCreate, ExportProfileUpdate, ProfileSectionIn
from schemas.profile import ATS_FONTS
from services.base import TransactionalService
from services.errors import ConflictError, InvalidDataError, NotFoundError, validate_model

# Recommended order (validator rule structure.section_order).
DEFAULT_SECTION_ORDER: tuple[SectionKey, ...] = (
    SectionKey.SUMMARY,
    SectionKey.EXPERIENCE,
    SectionKey.EDUCATION,
    SectionKey.SKILLS,
    SectionKey.PROJECTS,
    SectionKey.CERTIFICATIONS,
    SectionKey.LANGUAGES,
)
DEFAULT_THEME = "slate"
_PROFILE_FIELDS = tuple(ExportProfileCreate.model_fields)


def default_sections() -> list[ProfileSection]:
    return [
        ProfileSection(section=key, visible=True, position=i)
        for i, key in enumerate(DEFAULT_SECTION_ORDER)
    ]


def default_profiles() -> list[ExportProfile]:
    """The two profiles every new resume gets: "Plataforma" (ats) and "Correo" (mail)."""
    ats = ExportProfile(name="Plataforma", destination=Destination.ATS, font_family="Arial")
    mail = ExportProfile(
        name="Correo", destination=Destination.MAIL, theme=DEFAULT_THEME, date_format="MMM YYYY"
    )
    for profile in (ats, mail):
        profile.sections = default_sections()
    return [ats, mail]


class ProfileService(TransactionalService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def list(self, resume_id: int) -> list[ExportProfile]:
        if self.session.get(Resume, resume_id) is None:
            raise NotFoundError(f"No existe el CV con id {resume_id}")
        stmt = (
            select(ExportProfile)
            .where(ExportProfile.resume_id == resume_id)
            .order_by(ExportProfile.id)
        )
        return list(self.session.scalars(stmt))

    def get(self, profile_id: int, resume_id: int | None = None) -> ExportProfile:
        profile = self.session.get(ExportProfile, profile_id)
        if profile is None or (resume_id is not None and profile.resume_id != resume_id):
            raise NotFoundError(f"No existe el perfil con id {profile_id}")
        return profile

    def _check_name(self, resume_id: int, name: str, exclude_id: int | None) -> None:
        stmt = select(ExportProfile.id).where(
            ExportProfile.resume_id == resume_id,
            func.lower(ExportProfile.name) == name.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(ExportProfile.id != exclude_id)
        if self.session.scalar(stmt) is not None:
            raise ConflictError("Ya existe un perfil con ese nombre en este CV")

    def create(self, resume_id: int, data: ExportProfileCreate) -> ExportProfile:
        with self._write():
            self.list(resume_id)  # 404 if the resume does not exist
            self._check_name(resume_id, data.name, None)
            profile = ExportProfile(resume_id=resume_id, **data.model_dump())
            profile.sections = default_sections()
            self.session.add(profile)
            self.session.flush()
        return profile

    def update(
        self, profile_id: int, patch: ExportProfileUpdate, resume_id: int | None = None
    ) -> ExportProfile:
        with self._write():
            profile = self.get(profile_id, resume_id)
            changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
            destination = changes.get("destination", profile.destination)
            if destination == Destination.ATS:
                # Spec §4.5 rule 4: switching to ats clears mail-only fields.
                if profile.destination != Destination.ATS:
                    changes.update(include_photo=False, theme=None, accent_color=None)
                    if changes.get("font_family", profile.font_family) not in ATS_FONTS:
                        changes["font_family"] = "Arial"
            elif changes.get("theme", profile.theme) is None:
                changes["theme"] = DEFAULT_THEME
            current = {name: getattr(profile, name) for name in _PROFILE_FIELDS}
            validated = validate_model(ExportProfileCreate, {**current, **changes})
            if "name" in changes:
                self._check_name(profile.resume_id, validated.name, profile.id)
            for name in _PROFILE_FIELDS:
                setattr(profile, name, getattr(validated, name))
            self.session.flush()
        return profile

    def delete(self, profile_id: int, resume_id: int | None = None) -> None:
        profile = self.get(profile_id, resume_id)
        try:
            with self._write():
                self.session.delete(profile)
                self.session.flush()
        except ConflictError as exc:
            raise ConflictError(
                "El perfil tiene exportaciones asociadas y no se puede borrar"
            ) from exc

    def set_sections(
        self, profile_id: int, items: builtins.list[ProfileSectionIn]
    ) -> ExportProfile:
        """Full replacement of order + visibility + title of the 7 sections."""
        keys = [item.section for item in items]
        if len(keys) != len(set(keys)) or set(keys) != set(SectionKey):
            raise InvalidDataError.single(
                "sections", "Debes enviar las 7 secciones exactamente una vez"
            )
        with self._write():
            profile = self.get(profile_id)
            by_key = {s.section: s for s in profile.sections}
            for key in SectionKey:
                if key not in by_key:  # defensive: recreate a missing row
                    by_key[key] = ProfileSection(section=key, position=-100 - len(by_key))
                    profile.sections.append(by_key[key])
            for index, key in enumerate(keys):
                by_key[key].position = -(index + 1)
            self.session.flush()
            for index, item in enumerate(items):
                row = by_key[item.section]
                row.position = index
                row.visible = item.visible
                row.title_override = item.title_override
            self.session.flush()
        self.session.refresh(profile)
        return profile
