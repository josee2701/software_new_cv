"""Job posting match (spec §12, §14): keywords, technologies first, present/missing."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.seed import run_seed
from match.keywords import TechCatalog, analyzer, extract_keywords, html_to_text, tokens
from models import JobKeyword, JobPosting
from schemas import SkillCreate
from schemas.match import PostingCreate
from services import NotFoundError, SkillService
from services.match import MatchService

POSTING_ES = """Ingeniero(a) Backend Senior — Fintech en Bogotá.
Buscamos una persona con experiencia en Python, FastAPI y PostgreSQL, diseño de APIs REST
y arquitectura de microservicios. Deseable: Kubernetes, Terraform, Kafka y AWS.
Valoramos conocimientos de Rust y trabajo con metodologías ágiles (Scrum).
Responsabilidades: diseñar servicios de pagos de alto tráfico, mejorar la observabilidad
y acompañar a desarrolladores junior."""

POSTING_EN = """We are looking for a Senior Backend Engineer with strong Python and Go skills.
You will design event-driven microservices on AWS, using Docker, Kubernetes and GitHub Actions
for continuous delivery. Knowledge of GraphQL and Elasticsearch is a plus. Nice to have:
experience in payments and observability with OpenTelemetry."""


@pytest.fixture
def resume_id(session: Session) -> int:
    return run_seed(session).resume_id


def _terms(items: list[object]) -> list[str]:
    return [k.keyword for k in items]  # type: ignore[attr-defined]


def test_spanish_posting(session: Session, resume_id: int) -> None:
    result = MatchService(session).create_posting(
        resume_id, PostingCreate(title="Backend Senior", company="Fintech", raw_text=POSTING_ES)
    )
    present, missing = _terms(result.present), _terms(result.missing)
    for tech in ("Python", "FastAPI", "PostgreSQL", "Kubernetes", "Terraform", "Kafka", "AWS"):
        assert tech in present, (tech, present)
    assert "Rust" in missing and "Scrum" in missing
    assert "Microservicios" in present  # in the seeded technology catalog
    total = len(result.present) + len(result.missing)
    assert 10 <= total <= 40
    assert result.coverage == round(len(result.present) / total, 4)
    # technologies rank first and are flagged
    ranked = sorted(result.present + result.missing, key=lambda k: -k.weight)
    assert ranked[0].technology
    assert all(k.technology for k in result.present if k.keyword in {"Python", "AWS"})
    assert session.scalar(select(func.count()).select_from(JobKeyword)) == total
    assert result.posting.title == "Backend Senior"


def test_english_posting_and_recompute(session: Session, resume_id: int) -> None:
    service = MatchService(session)
    result = service.create_posting(resume_id, PostingCreate(title="Backend", raw_text=POSTING_EN))
    present, missing = _terms(result.present), _terms(result.missing)
    for tech in ("Python", "Go", "AWS", "Docker", "Kubernetes", "GitHub Actions", "OpenTelemetry"):
        assert tech in present, (tech, present)
    assert "GraphQL" in missing and "Elasticsearch" in missing

    # adding the missing skill to the CV flips it on the next GET
    category = SkillService(session).list(resume_id)[0]
    SkillService(session).skills.create(category.id, SkillCreate(name="GraphQL"))
    again = service.match(result.posting.id)
    assert "GraphQL" in _terms(again.present)
    assert again.coverage > result.coverage
    row = session.scalars(select(JobKeyword).where(JobKeyword.keyword == "GraphQL")).one()
    assert row.found_in_cv is True
    with pytest.raises(NotFoundError):
        service.match(999)


def test_keyword_units() -> None:
    assert tokens("Node.js, C++ y CI/CD.") == ["node.js", "c++", "y", "ci/cd"]
    assert "arquitectura microservicios" not in analyzer("arquitectura de microservicios")
    assert "servicios pagos" not in analyzer("servicios de pagos")
    assert "event-driven microservices" in analyzer("event-driven microservices")
    assert html_to_text("<style>p{color:red}</style><p>Hola &amp; adiós</p>") == "Hola & adiós"
    catalog = TechCatalog({"Go": "Go", "golang": "Go", "PostgreSQL": "PostgreSQL",
                           "postgres": "PostgreSQL"})  # fmt: skip
    assert catalog.in_text("Go", "Backend en Go y Python")
    assert not catalog.in_text("Go", "let's go live")  # short names are case-sensitive
    assert catalog.in_text("PostgreSQL", "bases de datos postgres")
    keywords = extract_keywords("Experiencia con Postgres y Go. Postgres avanzado.", "", catalog)
    assert [k.term for k in keywords if k.technology] == ["PostgreSQL", "Go"] or {
        k.term for k in keywords if k.technology
    } == {"PostgreSQL", "Go"}


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    from app.db import get_session
    from app.main import create_app

    app = create_app()

    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


def test_match_api(client: TestClient, session: Session, resume_id: int) -> None:
    r = client.post(
        f"/api/resumes/{resume_id}/postings",
        json={"title": "Backend", "company": "ACME", "raw_text": POSTING_ES},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"posting", "present", "missing", "coverage"}
    posting_id = body["posting"]["id"]
    again = client.get(f"/api/postings/{posting_id}/match").json()
    assert again["coverage"] == body["coverage"]
    assert session.get(JobPosting, posting_id) is not None
    assert client.get("/api/postings/999/match").status_code == 404
    short = client.post(
        f"/api/resumes/{resume_id}/postings", json={"title": "x", "raw_text": "corto"}
    )
    assert short.status_code == 422
    assert (
        client.post(
            "/api/resumes/999/postings", json={"title": "x", "raw_text": POSTING_EN}
        ).status_code
        == 404
    )
