"""Validation reports and export jobs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, IdMixin, TimestampMixin, str_enum, table_args
from models.enums import ExportFormat, ExportStatus, Severity

if TYPE_CHECKING:
    from models.export_profile import ExportProfile


class ValidationReport(IdMixin, TimestampMixin, Base):
    __tablename__ = "validation_report"
    __table_args__ = table_args(CheckConstraint("score >= 0 AND score <= 100", name="score"))

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("export_profile.id", ondelete="SET NULL"), index=True
    )
    score: Mapped[int] = mapped_column(Integer)
    errors: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    warnings: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    findings: Mapped[list[ValidationFinding]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="ValidationFinding.id"
    )


class ValidationFinding(IdMixin, TimestampMixin, Base):
    __tablename__ = "validation_finding"
    __table_args__ = table_args()

    report_id: Mapped[int] = mapped_column(
        ForeignKey("validation_report.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(60))
    severity: Mapped[Severity] = mapped_column(str_enum(Severity, 7))
    message: Mapped[str] = mapped_column(String(300))
    section: Mapped[str | None] = mapped_column(String(20))
    entity: Mapped[str | None] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    suggestion: Mapped[str | None] = mapped_column(String(300))

    report: Mapped[ValidationReport] = relationship(back_populates="findings")


class ExportJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "export_job"
    __table_args__ = table_args()

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("export_profile.id", ondelete="RESTRICT"), index=True
    )
    format: Mapped[ExportFormat] = mapped_column(str_enum(ExportFormat, 4))
    status: Mapped[ExportStatus] = mapped_column(
        str_enum(ExportStatus, 7),
        default=ExportStatus.PENDING,
        server_default=ExportStatus.PENDING.value,
    )
    output_path: Mapped[str | None] = mapped_column(String(500))
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("validation_report.id", ondelete="SET NULL"), index=True
    )
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("resume_snapshot.id", ondelete="SET NULL"), index=True
    )
    error: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[int | None] = mapped_column(Integer)
    roundtrip_ok: Mapped[bool | None] = mapped_column(Boolean)

    profile: Mapped[ExportProfile] = relationship()
