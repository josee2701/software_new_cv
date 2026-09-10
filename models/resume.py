from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, IdMixin, TimestampMixin, table_args

if TYPE_CHECKING:
    from models.audit import ExportJob, ValidationReport
    from models.basics import Basics, ContactLink
    from models.certification import Certification
    from models.education import Education
    from models.experience import Experience
    from models.export_profile import ExportProfile
    from models.job_posting import JobPosting
    from models.language import Language
    from models.project import Project
    from models.skill import SkillCategory

_CHILD = "all, delete-orphan"


class Resume(IdMixin, TimestampMixin, Base):
    __tablename__ = "resume"
    __table_args__ = table_args(
        CheckConstraint("language IN ('es', 'en')", name="language"),
        Index(
            "uq_resume_single_default",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )

    name: Mapped[str] = mapped_column(String(120), unique=True)
    language: Mapped[str] = mapped_column(String(5), default="es", server_default="es")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    notes: Mapped[str | None] = mapped_column(Text)

    basics: Mapped[Basics | None] = relationship(
        back_populates="resume", uselist=False, cascade=_CHILD
    )
    links: Mapped[list[ContactLink]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="ContactLink.position"
    )
    experiences: Mapped[list[Experience]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="Experience.position"
    )
    education: Mapped[list[Education]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="Education.position"
    )
    skill_categories: Mapped[list[SkillCategory]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="SkillCategory.position"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="Project.position"
    )
    certifications: Mapped[list[Certification]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="Certification.position"
    )
    languages: Mapped[list[Language]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="Language.position"
    )
    # export_jobs is declared before profiles so the ORM deletes jobs first
    # (export_job.profile_id is ON DELETE RESTRICT).
    export_jobs: Mapped[list[ExportJob]] = relationship(cascade=_CHILD, order_by="ExportJob.id")
    profiles: Mapped[list[ExportProfile]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="ExportProfile.id"
    )
    snapshots: Mapped[list[ResumeSnapshot]] = relationship(
        back_populates="resume", cascade=_CHILD, order_by="ResumeSnapshot.id"
    )
    validation_reports: Mapped[list[ValidationReport]] = relationship(
        cascade=_CHILD, order_by="ValidationReport.id"
    )
    job_postings: Mapped[list[JobPosting]] = relationship(cascade=_CHILD, order_by="JobPosting.id")


class ResumeSnapshot(IdMixin, TimestampMixin, Base):
    """Immutable version: full ``ResumeOut`` JSON dump."""

    __tablename__ = "resume_snapshot"
    __table_args__ = table_args()

    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    resume: Mapped[Resume] = relationship(back_populates="snapshots")
