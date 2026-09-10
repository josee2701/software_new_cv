from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, IdMixin, OrderedEntity, TimestampMixin, str_enum, table_args
from models.enums import Density, Destination, SectionKey

if TYPE_CHECKING:
    from models.resume import Resume

ATS_FONTS = ("Arial", "Calibri", "Helvetica", "Georgia")
DATE_FORMATS = ("MM/YYYY", "MMM YYYY", "YYYY")
_HEX = "[0-9A-Fa-f]" * 6


class ExportProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "export_profile"
    __table_args__ = table_args(
        UniqueConstraint("resume_id", "name"),
        CheckConstraint(
            "(destination = 'mail' AND theme IS NOT NULL) OR "
            "(destination = 'ats' AND theme IS NULL)",
            name="theme",
        ),
        CheckConstraint(
            f"accent_color IS NULL OR (destination = 'mail' AND accent_color GLOB '#{_HEX}')",
            name="accent_color",
        ),
        CheckConstraint("destination = 'mail' OR include_photo = 0", name="ats_no_photo"),
        CheckConstraint("max_pages IN (1, 2, 3)", name="max_pages"),
        CheckConstraint("date_format IN ('MM/YYYY', 'MMM YYYY', 'YYYY')", name="date_format"),
        CheckConstraint(
            "destination = 'mail' OR font_family IN ('Arial', 'Calibri', 'Helvetica', 'Georgia')",
            name="ats_font",
        ),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    destination: Mapped[Destination] = mapped_column(str_enum(Destination, 5))
    theme: Mapped[str | None] = mapped_column(String(40))
    accent_color: Mapped[str | None] = mapped_column(CHAR(7))
    density: Mapped[Density] = mapped_column(
        str_enum(Density, 10), default=Density.NORMAL, server_default=Density.NORMAL.value
    )
    include_photo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    max_pages: Mapped[int] = mapped_column(Integer, default=2, server_default=text("2"))
    date_format: Mapped[str] = mapped_column(
        String(12), default="MM/YYYY", server_default="MM/YYYY"
    )
    font_family: Mapped[str] = mapped_column(String(40), default="Arial", server_default="Arial")

    resume: Mapped[Resume] = relationship(back_populates="profiles")
    sections: Mapped[list[ProfileSection]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileSection.position"
    )


class ProfileSection(OrderedEntity):
    __tablename__ = "profile_section"
    __table_args__ = table_args(
        UniqueConstraint("profile_id", "section"),
        UniqueConstraint("profile_id", "position"),
    )

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("export_profile.id", ondelete="CASCADE"), index=True
    )
    section: Mapped[SectionKey] = mapped_column(str_enum(SectionKey, 20))
    visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    title_override: Mapped[str | None] = mapped_column(String(60))

    profile: Mapped[ExportProfile] = relationship(back_populates="sections")
