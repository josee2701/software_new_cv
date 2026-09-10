from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, OrderedEntity, OrderMixin, TimestampMixin, str_enum, table_args
from models.enums import ShowIn

if TYPE_CHECKING:
    from models.resume import Resume
    from models.technology import Technology


class Project(OrderedEntity):
    __tablename__ = "project"
    __table_args__ = table_args(
        UniqueConstraint("resume_id", "position"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="end_after_start",
        ),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(600))
    url: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    show_in: Mapped[ShowIn] = mapped_column(
        str_enum(ShowIn, 5), default=ShowIn.BOTH, server_default=ShowIn.BOTH.value
    )

    resume: Mapped[Resume] = relationship(back_populates="projects")
    technology_links: Mapped[list[ProjectTechnology]] = relationship(
        cascade="all, delete-orphan", order_by="ProjectTechnology.position"
    )

    @property
    def technologies(self) -> list[str]:
        return [link.technology.canonical for link in self.technology_links]


class ProjectTechnology(TimestampMixin, OrderMixin, Base):
    __tablename__ = "project_technology"
    __table_args__ = (UniqueConstraint("project_id", "position"),)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    technology_id: Mapped[int] = mapped_column(
        ForeignKey("technology.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    technology: Mapped[Technology] = relationship(lazy="joined")
