from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import OrderedEntity, str_enum, table_args
from models.enums import ShowIn, SkillLevel

if TYPE_CHECKING:
    from models.resume import Resume
    from models.technology import Technology


class SkillCategory(OrderedEntity):
    __tablename__ = "skill_category"
    __table_args__ = table_args(
        UniqueConstraint("resume_id", "name"),
        UniqueConstraint("resume_id", "position"),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))

    resume: Mapped[Resume] = relationship(back_populates="skill_categories")
    skills: Mapped[list[Skill]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="Skill.position"
    )


class Skill(OrderedEntity):
    __tablename__ = "skill"
    __table_args__ = table_args(
        UniqueConstraint("category_id", "name"),
        UniqueConstraint("category_id", "position"),
        CheckConstraint("years IS NULL OR (years >= 0 AND years <= 50)", name="years"),
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("skill_category.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    level: Mapped[SkillLevel | None] = mapped_column(str_enum(SkillLevel, 12))
    years: Mapped[int | None] = mapped_column(Integer)
    technology_id: Mapped[int | None] = mapped_column(
        ForeignKey("technology.id", ondelete="SET NULL"), index=True
    )
    show_in: Mapped[ShowIn] = mapped_column(
        str_enum(ShowIn, 5), default=ShowIn.BOTH, server_default=ShowIn.BOTH.value
    )

    category: Mapped[SkillCategory] = relationship(back_populates="skills")
    technology: Mapped[Technology | None] = relationship()
