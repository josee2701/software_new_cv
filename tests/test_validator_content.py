"""``content.*`` rules: positive/negative cases and severity per destination."""

from __future__ import annotations

import pytest

from tests.validator_factories import (
    SUMMARY,
    ach,
    category,
    check,
    exp,
    make_ctx,
    make_cv,
    make_profile,
    sections,
    severities,
)

VERB_TEXT = "Lideré la migración de 3 servicios a Kubernetes, reduciendo 40% los costos."


def _cv_with(achievements: list[dict[str, object]], **exp_kw: object) -> object:
    return make_cv(experiences=[exp(1, achievements=achievements, **exp_kw)])


# ------------------------------------------------------------------ summary


@pytest.mark.parametrize("summary", ["", "Corto.", "x" * 601])
@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_summary_length(summary: str, dest: str) -> None:
    ctx = make_ctx(dest, cv=make_cv({"summary": summary}))
    assert severities("content.summary_length", ctx) == {"warning"}
    assert check("content.summary_length", make_ctx(dest)) == []


def test_summary_length_skipped_when_hidden() -> None:
    profile = make_profile("ats", sections=sections(summary={"visible": False}))
    ctx = make_ctx("ats", cv=make_cv({"summary": ""}), profile=profile)
    assert check("content.summary_length", ctx) == []


@pytest.mark.parametrize(("dest", "expected"), [("ats", "warning"), ("mail", "info")])
def test_summary_first_person(dest: str, expected: str) -> None:
    ctx = make_ctx(dest, cv=make_cv({"summary": "Yo soy ingeniera. " + SUMMARY + " Mi meta."}))
    (finding,) = check("content.summary_first_person", ctx)
    assert finding.severity.value == expected
    assert "«mi», «yo»" in finding.message
    assert check("content.summary_first_person", make_ctx(dest)) == []


def test_summary_first_person_english_and_preterite_is_not_pronoun() -> None:
    en = make_cv({"summary": "I build APIs and my focus is quality."}, language="en")
    assert check("content.summary_first_person", make_ctx("ats", cv=en)) != []
    es = make_cv({"summary": "Lideré equipos y diseñé plataformas de pagos."})
    assert check("content.summary_first_person", make_ctx("ats", cv=es)) == []


# ------------------------------------------------------------------ achievements


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_min_achievements(dest: str) -> None:
    cv = _cv_with([ach(1, VERB_TEXT)])
    (finding,) = check("content.min_achievements", make_ctx(dest, cv=cv))
    assert finding.severity.value == "warning"
    assert (finding.entity, finding.entity_id) == ("experience", 1)
    short = _cv_with([ach(1, VERB_TEXT)], start_date="2021-01-01", end_date="2021-04-01")
    assert check("content.min_achievements", make_ctx(dest, cv=short)) == []
    assert check("content.min_achievements", make_ctx(dest)) == []


def test_min_achievements_counts_only_destination() -> None:
    cv = _cv_with([ach(1, VERB_TEXT), ach(2, VERB_TEXT, show_in="mail")])
    assert check("content.min_achievements", make_ctx("ats", cv=cv)) != []
    assert check("content.min_achievements", make_ctx("mail", cv=cv)) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_max_achievements(dest: str) -> None:
    cv = _cv_with([ach(i, VERB_TEXT) for i in range(7)])
    assert severities("content.max_achievements", make_ctx(dest, cv=cv)) == {"info"}
    six = _cv_with([ach(i, VERB_TEXT) for i in range(6)])
    assert check("content.max_achievements", make_ctx(dest, cv=six)) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_action_verb(dest: str) -> None:
    text = "Responsable de la migración de 3 servicios a la nube con AWS."
    cv = _cv_with([ach(1, text), ach(2, VERB_TEXT)])
    (finding,) = check("content.action_verb", make_ctx(dest, cv=cv))
    assert finding.severity.value == "warning"
    assert (finding.entity, finding.entity_id) == ("achievement", 1)
    variants = ["LIDERÉ el equipo de 5 personas en la migración.", "lidere 3 proyectos"]
    cv = _cv_with([ach(i, t + " de pagos a la nube") for i, t in enumerate(variants)])
    assert check("content.action_verb", make_ctx(dest, cv=cv)) == []


def test_action_verb_english() -> None:
    cv = make_cv(
        language="en",
        experiences=[
            exp(1, achievements=[ach(1, "Led the migration of 3 services."), ach(2, "The team.")])
        ],
    )
    findings = check("content.action_verb", make_ctx("ats", cv=cv))
    assert [f.entity_id for f in findings] == [2]


@pytest.mark.parametrize(("dest", "expected"), [("ats", "warning"), ("mail", "info")])
def test_metric(dest: str, expected: str) -> None:
    plain = "Lideré la migración de los servicios de pagos a la nube pública."
    cv = _cv_with([ach(1, plain), ach(2, plain), ach(3, VERB_TEXT)])
    (finding,) = check("content.metric", make_ctx(dest, cv=cv))
    assert finding.severity.value == expected and "1 de 3" in finding.message
    one_of_three = _cv_with([ach(1, plain, metric="2x"), ach(2, plain), ach(3, plain)])
    assert check("content.metric", make_ctx(dest, cv=one_of_three)) != []  # 33% < 40%
    two_of_three = _cv_with([ach(1, plain, metric="2x"), ach(2, plain, metric="3"), ach(3, plain)])
    assert check("content.metric", make_ctx(dest, cv=two_of_three)) == []
    assert check("content.metric", make_ctx(dest, cv=make_cv(experiences=[]))) == []


def test_metric_currency_and_ratio() -> None:
    plain = "Lideré la migración de los servicios de pagos a la nube pública."
    money = "Negocié contratos con proveedores ahorrando USD cien mil al año."
    cv = _cv_with([ach(1, money), ach(2, plain)])
    assert check("content.metric", make_ctx("ats", cv=cv)) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_achievement_length(dest: str) -> None:
    cv = _cv_with([ach(1, "Lideré 3 cosas."), ach(2, "Lideré " + "x" * 230), ach(3, VERB_TEXT)])
    findings = check("content.achievement_length", make_ctx(dest, cv=cv))
    assert [f.entity_id for f in findings] == [1, 2]
    assert {f.severity.value for f in findings} == {"warning"}
    assert "corto" in findings[0].message and "largo" in findings[1].message


def test_no_pronouns_ats_info_only() -> None:
    text = "Lideré con mi equipo la migración de 3 servicios críticos a la nube."
    cv = _cv_with([ach(1, text), ach(2, VERB_TEXT)])
    (finding,) = check("content.no_pronouns", make_ctx("ats", cv=cv))
    assert finding.severity.value == "info" and "mi" in finding.message
    assert check("content.no_pronouns", make_ctx("mail", cv=cv)) == []
    en = make_cv(language="en", experiences=[exp(1, achievements=[ach(1, "We shipped 3 apps.")])])
    assert check("content.no_pronouns", make_ctx("ats", cv=en)) != []
    assert check("content.no_pronouns", make_ctx("ats")) == []


# ------------------------------------------------------------------ skills


@pytest.mark.parametrize(("dest", "expected"), [("ats", "error"), ("mail", "warning")])
def test_skills_present(dest: str, expected: str) -> None:
    few = make_cv(skill_categories=[category(1, "Lenguajes", ["Python", "Go", "SQL"])])
    (finding,) = check("content.skills_present", make_ctx(dest, cv=few))
    assert finding.severity.value == expected and "3 habilidad" in finding.message
    hidden = make_profile(dest, sections=sections(skills={"visible": False}))
    assert check("content.skills_present", make_ctx(dest, profile=hidden)) != []
    assert check("content.skills_present", make_ctx(dest)) == []


@pytest.mark.parametrize("name", ["Python 90%", "Go ★★★☆", "SQL (Avanzado)", "Docker 8/10"])
def test_skills_no_levels_ats(name: str) -> None:
    cv = make_cv(skill_categories=[category(1, "A", ["Java", "C", "Rust", "Ruby", name])])
    (finding,) = check("content.skills_no_levels_ats", make_ctx("ats", cv=cv))
    assert finding.severity.value == "warning" and finding.entity == "skill"
    assert check("content.skills_no_levels_ats", make_ctx("mail", cv=cv)) == []


def test_skills_no_levels_html_bars() -> None:
    html = "<p>Python <progress value=9 max=10></progress></p>"
    assert check("content.skills_no_levels_ats", make_ctx("ats", html=html)) != []
    assert check("content.skills_no_levels_ats", make_ctx("ats", html="<p>ok</p>")) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_keywords_from_experience(dest: str) -> None:
    cv = make_cv(experiences=[exp(1, technologies=["Python", "Rust", "rust", "Elixir"])])
    (finding,) = check("content.keywords_from_experience", make_ctx(dest, cv=cv))
    assert finding.severity.value == "info"
    assert "Rust, Elixir." in finding.message
    many = make_cv(experiences=[exp(1, technologies=[f"T{i}" for i in range(15)])])
    (finding,) = check("content.keywords_from_experience", make_ctx(dest, cv=many))
    assert finding.message.endswith("….")
    assert check("content.keywords_from_experience", make_ctx(dest)) == []


@pytest.mark.parametrize("dest", ["ats", "mail"])
def test_duplicate_skill(dest: str) -> None:
    cv = make_cv(
        skill_categories=[
            category(1, "Lenguajes", ["Python", "Go", "SQL"]),
            category(2, "Backend", ["python", "Docker", "AWS"]),
        ]
    )
    (finding,) = check("content.duplicate_skill", make_ctx(dest, cv=cv))
    assert finding.severity.value == "warning"
    assert (finding.entity, finding.entity_id) == ("skill", 200)
    assert check("content.duplicate_skill", make_ctx(dest)) == []
