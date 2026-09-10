from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, IdMixin, OrderedEntity, TimestampMixin, str_enum, table_args
from models.enums import LinkKind

if TYPE_CHECKING:
    from models.asset import Asset
    from models.resume import Resume


class Basics(IdMixin, TimestampMixin, Base):
    __tablename__ = "basics"
    __table_args__ = table_args(
        CheckConstraint("summary IS NULL OR length(summary) <= 1200", name="summary_length"),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    headline: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(30))
    city: Mapped[str] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2))
    summary: Mapped[str | None] = mapped_column(Text)
    photo_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset.id", ondelete="SET NULL"), index=True
    )

    resume: Mapped[Resume] = relationship(back_populates="basics")
    photo: Mapped[Asset | None] = relationship()


class ContactLink(OrderedEntity):
    __tablename__ = "contact_link"
    __table_args__ = table_args(UniqueConstraint("resume_id", "position"))

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    kind: Mapped[LinkKind] = mapped_column(str_enum(LinkKind, 20))
    label: Mapped[str | None] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))

    resume: Mapped[Resume] = relationship(back_populates="links")
