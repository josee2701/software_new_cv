from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import OrderedEntity, str_enum, table_args
from models.enums import DegreeLevel, ShowIn

if TYPE_CHECKING:
    from models.resume import Resume


class Education(OrderedEntity):
    __tablename__ = "education"
    __table_args__ = table_args(UniqueConstraint("resume_id", "position"))

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str] = mapped_column(String(160))
    degree: Mapped[str] = mapped_column(String(160))
    level: Mapped[DegreeLevel | None] = mapped_column(str_enum(DegreeLevel, 20))
    field: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    in_progress: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    gpa: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(String(400))
    show_in: Mapped[ShowIn] = mapped_column(
        str_enum(ShowIn, 5), default=ShowIn.BOTH, server_default=ShowIn.BOTH.value
    )

    resume: Mapped[Resume] = relationship(back_populates="education")
