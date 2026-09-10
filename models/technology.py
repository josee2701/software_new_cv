from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, IdMixin, TimestampMixin, table_args


class Technology(IdMixin, TimestampMixin, Base):
    """Normalized technology catalog (``name`` may be an alias of ``canonical``)."""

    __tablename__ = "technology"
    __table_args__ = table_args()

    name: Mapped[str] = mapped_column(String(60, collation="NOCASE"), unique=True)
    canonical: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str | None] = mapped_column(String(40))
