"""Validator engine, registry, score and catalog (spec §9.1, §9.2; DECISIONS.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.enums import Destination, Severity
from render.renderer import render
from tests.validator_factories import GOOD_PDF, check, make_ctx, make_cv, make_profile
from validator import text
from validator.docs import rules_markdown
from validator.engine import applicable_rules, compute_score, run
from validator.registry import get_rule, load_rules, make_spec, registered_rules, rule
from validator.types import Hit, Phase, RuleContext

ROOT = Path(__file__).resolve().parent.parent

# Spec §9.2: id → (ats, mail, weight); "-" = does not run.
SPEC_TABLE: dict[str, tuple[str, str, int]] = {
    "contact.email_present": ("error", "error", 15),
    "contact.phone_present": ("error", "warning", 10),
    "contact.location_present": ("warning", "info", 3),
    "contact.linkedin_present": ("warning", "info", 3),
    "contact.url_plain": ("error", "-", 5),
    "structure.single_column": ("error", "-", 15),
    "structure.no_tables": ("error", "-", 15),
    "structure.no_photo": ("error", "-", 10),
    "structure.section_order": ("warning", "-", 5),
    "structure.canonical_headings": ("error", "-", 8),
    "structure.required_sections": ("error", "warning", 10),
    "content.summary_length": ("warning", "warning", 4),
    "content.summary_first_person": ("warning", "info", 2),
    "content.min_achievements": ("warning", "warning", 5),
    "content.max_achievements": ("info", "info", 1),
    "content.action_verb": ("warning", "warning", 3),
    "content.metric": ("warning", "info", 3),
    "content.achievement_length": ("warning", "warning", 2),
    "content.no_pronouns": ("info", "-", 1),
    "content.skills_present": ("error", "warning", 8),
    "content.skills_no_levels_ats": ("warning", "-", 2),
    "content.keywords_from_experience": ("info", "info", 2),
    "content.duplicate_skill": ("warning", "warning", 2),
    "dates.format_consistent": ("error", "warning", 6),
    "dates.chronological": ("warning", "info", 3),
    "dates.gap": ("info", "-", 1),
    "dates.overlap_current": ("warning", "warning", 2),
    "dates.future": ("error", "error", 5),
    "dates.end_before_start": ("error", "error", 5),
    "length.pages": ("error", "warning", 10),
    "length.min_content": ("warning", "warning", 4),
    "technical.text_extractable": ("error", "warning", 20),
    "technical.fonts_embedded": ("error", "info", 5),
    "technical.no_special_chars": ("warning", "-", 3),
    "technical.filename": ("warning", "warning", 1),
    "technical.metadata": ("info", "info", 1),
    "photo.present_mail": ("-", "info", 1),
    "photo.warning_region": ("-", "warning", 2),
}


def _sev(value: str) -> Severity | None:
    return None if value == "-" else Severity(value)


# ------------------------------------------------------------------ catalog


def test_registry_matches_spec_catalog() -> None:
    specs = {s.id: s for s in registered_rules()}
    assert set(specs) == set(SPEC_TABLE)
    for rule_id, (ats, mail, weight) in SPEC_TABLE.items():
        spec = specs[rule_id]
        assert spec.severity_for(Destination.ATS) == _sev(ats), rule_id
        assert spec.severity_for(Destination.MAIL) == _sev(mail), rule_id
        assert spec.weight == weight, rule_id
        assert spec.description, rule_id
        expected_phase = Phase.POST if rule_id.startswith("technical.") else Phase.PRE
        assert spec.phase is expected_phase, rule_id


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_good_cv_has_no_findings_with_every_input(dest: str) -> None:
    cv, profile = make_cv(), make_profile(dest)
    html = render(cv, profile).html
    report = run(make_ctx(dest, cv=cv, profile=profile, html=html, pages=2, pdf=GOOD_PDF))
    assert report.findings == ()
    assert report.score == 100


def test_docs_file_is_generated_from_registry() -> None:
    doc = rules_markdown()
    assert (ROOT / "docs" / "ATS_RULES.md").read_text(encoding="utf-8") == doc
    for rule_id in SPEC_TABLE:
        assert f"`{rule_id}`" in doc
    assert "| `photo.present_mail` | basics | – | info | 1 | pre |" in doc


# ------------------------------------------------------------------ registry


def _noop(ctx: RuleContext) -> list[Hit]:
    """Regla de prueba."""
    return []


def test_make_spec_parses_severities_and_skips() -> None:
    spec = make_spec(
        id="x.a", section="s", severity={"ats": "error", "mail": "–"}, weight=4, fn=_noop
    )
    assert spec.severity_for(Destination.ATS) is Severity.ERROR
    assert spec.severity_for(Destination.MAIL) is None
    assert spec.runs_for(Destination.ATS) and not spec.runs_for(Destination.MAIL)
    assert spec.description == "Regla de prueba."
    spec = make_spec(id="x.b", section="s", severity={"mail": "info"}, weight=1, fn=_noop)
    assert not spec.runs_for(Destination.ATS)
    with pytest.raises(ValueError, match="peso"):
        make_spec(id="x.c", section="s", severity={}, weight=-1, fn=_noop)
    with pytest.raises(ValueError):
        make_spec(id="x.d", section="s", severity={"ats": "fatal"}, weight=1, fn=_noop)


def test_rule_decorator_rejects_duplicate_ids() -> None:
    spec = get_rule("contact.email_present")
    decorator = rule(id="contact.email_present", section="basics", severity={}, weight=1)
    with pytest.raises(ValueError, match="duplicada"):
        decorator(_noop)
    assert decorator(spec.fn) is spec.fn  # re-registering the same function is idempotent
    load_rules()
    assert get_rule("contact.email_present").weight == 15


# ------------------------------------------------------------------ engine and score


def _fixed(message: str, count: int = 1) -> object:
    def fn(ctx: RuleContext) -> list[Hit]:
        return [Hit(f"{message} {i}") for i in range(count)]

    return fn


def _spec(rule_id: str, ats: str, mail: str, weight: int, count: int = 1, **kw: object):  # type: ignore[no-untyped-def]
    return make_spec(
        id=rule_id,
        section="sec",
        severity={"ats": ats, "mail": mail},
        weight=weight,
        fn=_fixed(rule_id, count),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


def test_score_discounts_each_rule_once() -> None:
    specs = [
        _spec("r.error", "error", "warning", 10, count=3),
        _spec("r.warning", "warning", "info", 5),
        _spec("r.info", "info", "info", 7),
    ]
    ats = run(make_ctx("ats"), rules=specs)
    assert ats.score == 87  # 100 - 10 (once, 3 hits) - 5/2 = 87.5, rounded down
    assert (ats.errors, ats.warnings, len(ats.findings)) == (3, 1, 5)
    assert ats.blocks_export(Destination.ATS)
    mail = run(make_ctx("mail"), rules=specs)
    assert mail.score == 100 - 5
    assert mail.errors == 0 and not mail.blocks_export(Destination.MAIL)


def test_score_minimum_zero_and_rounding() -> None:
    assert compute_score([60, 50]) == 0
    assert compute_score([2.5]) == 97
    assert compute_score([]) == 100


def test_findings_sorted_by_severity_then_rule_order() -> None:
    specs = [
        _spec("a.info", "info", "info", 1),
        _spec("b.warning", "warning", "warning", 1, count=2),
        _spec("c.error", "error", "error", 1),
    ]
    report = run(make_ctx("ats"), rules=specs)
    assert [f.rule_id for f in report.findings] == ["c.error", "b.warning", "b.warning", "a.info"]
    assert [f.message for f in report.findings][1:3] == ["b.warning 0", "b.warning 1"]
    assert report.findings[0].section == "sec"  # rule section when the hit has none


def test_hit_fields_are_copied_to_finding() -> None:
    def fn(ctx: RuleContext) -> list[Hit]:
        return [Hit("m", section="skills", entity="skill", entity_id=7, suggestion="s")]

    spec = make_spec(id="z.z", section="x", severity={"ats": "warning"}, weight=2, fn=fn)
    (finding,) = run(make_ctx("ats"), rules=[spec]).findings
    assert (finding.rule_id, finding.severity) == ("z.z", Severity.WARNING)
    assert finding.section == "skills"
    assert (finding.entity, finding.entity_id, finding.suggestion) == ("skill", 7, "s")


def test_post_rules_only_run_with_pdf_and_destination_filter() -> None:
    pre = _spec("p.pre", "error", "-", 1)
    post = _spec("p.post", "error", "error", 1, phase=Phase.POST)
    assert applicable_rules(make_ctx("ats"), [pre, post]) == [pre]
    assert applicable_rules(make_ctx("ats", pdf=GOOD_PDF), [pre, post]) == [pre, post]
    assert applicable_rules(make_ctx("mail", pdf=GOOD_PDF), [pre, post]) == [post]
    assert {s.id for s in applicable_rules(make_ctx("ats"))} == {
        rid for rid, (ats, _, _) in SPEC_TABLE.items() if ats != "-" and "technical" not in rid
    }


def test_check_helper_runs_a_single_rule() -> None:
    ctx = make_ctx("ats", cv=make_cv({"email": ""}))
    assert [f.rule_id for f in check("contact.email_present", ctx)] == ["contact.email_present"]


# ------------------------------------------------------------------ text helpers and word lists


def test_fold_words_and_first_word() -> None:
    assert text.fold("Lideré AÑO") == "lidere ano"
    assert text.words("I'm here, yo; mí") == ["im", "here", "yo", "mi"]
    assert text.first_word("• 3 Reduje costos") == "reduje"
    assert text.first_word("123") == ""
    assert text.lang_or_default("fr") == "es"


def test_html_helpers() -> None:
    html = (
        "<html><head><title>T</title><style>p{color:red}</style></head>"
        "<body><p>Hola <b>mundo</b></p><a href='https://x.com'>x.com</a></body></html>"
    )
    assert text.html_text(html) == "Hola mundo x.com"
    assert text.html_anchors(html) == [("https://x.com", "x.com")]
    assert text.strip_comments("a/* b */c<!-- d -->e") == "a c e"


@pytest.mark.parametrize(("lang", "forms"), [("es", 3), ("en", 2)])
def test_verb_lists(lang: str, forms: int) -> None:
    lines = text.verb_lines(lang)
    assert len(lines) >= 150
    assert all(len(row) >= forms for row in lines)
    assert len({row[0] for row in lines}) == len(lines)  # one line per verb


def test_spanish_verbs_cover_preterite_forms() -> None:
    verbs = text.action_verbs("es")
    for word in ("liderar", "lideré", "lideró", "reduje", "construí", "construyó", "mentoricé"):
        assert text.fold(word) in verbs
    assert {"led", "lead", "designed", "planned"} <= text.action_verbs("en")
