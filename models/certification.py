from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import OrderedEntity, str_enum, table_args
from models.enums import ShowIn

if TYPE_CHECKING:
    from models.resume import Resume


class Certification(OrderedEntity):
    __tablename__ = "certification"
    __table_args__ = table_args(
        UniqueConstraint("resume_id", "position"),
        CheckConstraint(
            "expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date",
            name="expiry_after_issue",
        ),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    issuer: Mapped[str] = mapped_column(String(120))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    credential_id: Mapped[str | None] = mapped_column(String(80))
    url: Mapped[str | None] = mapped_column(String(500))
    show_in: Mapped[ShowIn] = mapped_column(
        str_enum(ShowIn, 5), default=ShowIn.BOTH, server_default=ShowIn.BOTH.value
    )

    resume: Mapped[Resume] = relationship(back_populates="certifications")
