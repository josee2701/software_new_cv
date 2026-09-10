from __future__ import annotations

from sqlalchemy import CHAR, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, IdMixin, TimestampMixin, table_args

MAX_ASSET_BYTES = 5_000_000
ALLOWED_MIME = ("image/jpeg", "image/png", "image/webp")


class Asset(IdMixin, TimestampMixin, Base):
    """Uploaded file (profile photo) stored under ``data/uploads/``."""

    __tablename__ = "asset"
    __table_args__ = table_args(
        CheckConstraint("mime IN ('image/jpeg', 'image/png', 'image/webp')", name="mime"),
        CheckConstraint(f"size_bytes <= {MAX_ASSET_BYTES}", name="size_bytes"),
    )

    filename: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(50))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(CHAR(64), unique=True)
