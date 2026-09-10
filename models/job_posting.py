from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, IdMixin, TimestampMixin, table_args


class JobPosting(IdMixin, TimestampMixin, Base):
    __tablename__ = "job_posting"
    __table_args__ = table_args()

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    company: Mapped[str | None] = mapped_column(String(120))
    raw_text: Mapped[str] = mapped_column(Text)

    keywords: Mapped[list[JobKeyword]] = relationship(
        back_populates="posting", cascade="all, delete-orphan", order_by="JobKeyword.id"
    )


class JobKeyword(IdMixin, TimestampMixin, Base):
    __tablename__ = "job_keyword"
    __table_args__ = table_args(UniqueConstraint("posting_id", "keyword"))

    posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), index=True
    )
    keyword: Mapped[str] = mapped_column(String(60))
    weight: Mapped[float] = mapped_column(Float)
    found_in_cv: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))

    posting: Mapped[JobPosting] = relationship(back_populates="keywords")
