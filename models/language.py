from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import OrderedEntity, str_enum, table_args
from models.enums import LanguageLevel

if TYPE_CHECKING:
    from models.resume import Resume


class Language(OrderedEntity):
    __tablename__ = "language"
    __table_args__ = table_args(
        UniqueConstraint("resume_id", "name"),
        UniqueConstraint("resume_id", "position"),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    level: Mapped[LanguageLevel] = mapped_column(str_enum(LanguageLevel, 6))

    resume: Mapped[Resume] = relationship(back_populates="languages")
