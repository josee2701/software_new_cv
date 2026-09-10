from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, OrderedEntity, OrderMixin, TimestampMixin, str_enum, table_args
from models.enums import ShowIn

if TYPE_CHECKING:
    from models.resume import Resume
    from models.technology import Technology


class Experience(OrderedEntity):
    __tablename__ = "experience"
    __table_args__ = table_args(
        UniqueConstraint("resume_id", "position"),
        CheckConstraint(
            "(is_current = 1 AND end_date IS NULL) OR (is_current = 0 AND end_date IS NOT NULL)",
            name="current_end_date",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="end_after_start"),
        CheckConstraint(
            "description IS NULL OR length(description) <= 400", name="description_length"
        ),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    employment_type: Mapped[str | None] = mapped_column(String(30))
    city: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(2))
    remote: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    description: Mapped[str | None] = mapped_column(Text)
    show_in: Mapped[ShowIn] = mapped_column(
        str_enum(ShowIn, 5), default=ShowIn.BOTH, server_default=ShowIn.BOTH.value
    )

    resume: Mapped[Resume] = relationship(back_populates="experiences")
    achievements: Mapped[list[Achievement]] = relationship(
        back_populates="experience", cascade="all, delete-orphan", order_by="Achievement.position"
    )
    technology_links: Mapped[list[ExperienceTechnology]] = relationship(
        cascade="all, delete-orphan", order_by="ExperienceTechnology.position"
    )

    @property
    def technologies(self) -> list[str]:
        return [link.technology.canonical for link in self.technology_links]


Index("ix_experience_resume_start", Experience.resume_id, Experience.start_date.desc())


class Achievement(OrderedEntity):
    __tablename__ = "achievement"
    __table_args__ = table_args(UniqueConstraint("experience_id", "position"))

    experience_id: Mapped[int] = mapped_column(
        ForeignKey("experience.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(String(300))
    metric_value: Mapped[str | None] = mapped_column(String(40))
    show_in: Mapped[ShowIn] = mapped_column(
        str_enum(ShowIn, 5), default=ShowIn.BOTH, server_default=ShowIn.BOTH.value
    )

    experience: Mapped[Experience] = relationship(back_populates="achievements")


class ExperienceTechnology(TimestampMixin, OrderMixin, Base):
    __tablename__ = "experience_technology"
    __table_args__ = (UniqueConstraint("experience_id", "position"),)

    experience_id: Mapped[int] = mapped_column(
        ForeignKey("experience.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    technology_id: Mapped[int] = mapped_column(
        ForeignKey("technology.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    technology: Mapped[Technology] = relationship(lazy="joined")
