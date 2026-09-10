"""Domain enums (spec §4.3). Stored as VARCHAR + CHECK."""

from enum import StrEnum


class Destination(StrEnum):
    ATS = "ats"
    MAIL = "mail"


class Density(StrEnum):
    COMPACT = "compact"
    NORMAL = "normal"
    WIDE = "wide"


class ShowIn(StrEnum):
    ATS = "ats"
    MAIL = "mail"
    BOTH = "both"


class SectionKey(StrEnum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"


class LinkKind(StrEnum):
    LINKEDIN = "linkedin"
    GITHUB = "github"
    WEBSITE = "website"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class DegreeLevel(StrEnum):
    TECHNICAL = "technical"
    TECHNOLOGIST = "technologist"
    BACHELOR = "bachelor"
    SPECIALIZATION = "specialization"
    MASTER = "master"
    PHD = "phd"
    COURSE = "course"
    OTHER = "other"


class LanguageLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    NATIVE = "native"


class SkillLevel(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ExportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    JSON = "json"


class ExportStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
