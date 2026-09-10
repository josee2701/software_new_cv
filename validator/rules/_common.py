"""Helpers shared by rule modules: what is visible for the destination, dates."""

from __future__ import annotations

from datetime import date

from models.enums import SectionKey, ShowIn
from schemas import (
    AchievementOut,
    ExperienceOut,
    ProfileSectionOut,
    SkillOut,
)
from validator.types import RuleContext


def today() -> date:
    """Current date (patched in tests)."""
    return date.today()


def shown(ctx: RuleContext, show_in: ShowIn) -> bool:
    """``show_in`` allows the item in the profile destination."""
    return show_in is ShowIn.BOTH or show_in.value == ctx.destination.value


def section(ctx: RuleContext, key: SectionKey) -> ProfileSectionOut | None:
    return next((s for s in ctx.profile.sections if s.section is key), None)


def section_visible(ctx: RuleContext, key: SectionKey) -> bool:
    """A section missing from the profile counts as hidden."""
    ps = section(ctx, key)
    return ps is not None and ps.visible


def visible_sections(ctx: RuleContext) -> list[ProfileSectionOut]:
    return [s for s in sorted(ctx.profile.sections, key=lambda s: s.position) if s.visible]


def experiences(ctx: RuleContext) -> list[ExperienceOut]:
    """Experiences shown for the destination, in ``position`` order (ignores section visibility)."""
    items = sorted(ctx.cv.experiences, key=lambda e: e.position)
    return [e for e in items if shown(ctx, e.show_in)]


def achievements(ctx: RuleContext, exp: ExperienceOut) -> list[AchievementOut]:
    items = sorted(exp.achievements, key=lambda a: a.position)
    return [a for a in items if shown(ctx, a.show_in)]


def all_achievements(ctx: RuleContext) -> list[AchievementOut]:
    return [a for exp in experiences(ctx) for a in achievements(ctx, exp)]


def skills(ctx: RuleContext) -> list[SkillOut]:
    """Skills shown for the destination in category/position order."""
    result: list[SkillOut] = []
    for cat in sorted(ctx.cv.skill_categories, key=lambda c: c.position):
        result.extend(
            s for s in sorted(cat.skills, key=lambda s: s.position) if shown(ctx, s.show_in)
        )
    return result


def months_between(start: date, end: date) -> int:
    """Whole months from ``start`` to ``end`` (dates are stored with day 01)."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def month_start(value: date) -> date:
    return value.replace(day=1)


def excerpt(text: str, size: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"
