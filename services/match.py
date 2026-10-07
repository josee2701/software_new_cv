"""Job posting match (spec §12): keywords persisted in ``job_posting`` / ``job_keyword``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from match.keywords import Keyword, TechCatalog, extract_keywords, found_in_cv, html_to_text
from models import JobKeyword, JobPosting, Technology
from models.enums import Destination
from render.renderer import render
from schemas.match import KeywordOut, MatchResultOut, PostingCreate, PostingOut
from services.base import TransactionalService
from services.errors import NotFoundError
from services.resume import ResumeService


class MatchService(TransactionalService):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def catalog(self) -> TechCatalog:
        rows = self.session.execute(select(Technology.name, Technology.canonical)).all()
        names: dict[str, str] = {}
        for name, canonical in rows:
            names[name] = canonical
            names[canonical] = canonical
        return TechCatalog(names)

    def cv_text(self, resume_id: int) -> str:
        """Plain text of the CV rendered with its ats profile (spec §12.3)."""
        cv = ResumeService(self.session).get_out(resume_id)
        profiles = sorted(cv.profiles, key=lambda p: p.destination is not Destination.ATS)
        if not profiles:
            return ""
        return html_to_text(render(cv, profiles[0]).html)

    def get_posting(self, posting_id: int) -> JobPosting:
        posting = self.session.get(JobPosting, posting_id)
        if posting is None:
            raise NotFoundError(f"No existe la vacante con id {posting_id}")
        return posting

    def create_posting(self, resume_id: int, data: PostingCreate) -> MatchResultOut:
        cv_text = self.cv_text(resume_id)  # 404 if the resume does not exist
        catalog = self.catalog()
        keywords = extract_keywords(data.raw_text, cv_text, catalog)
        with self._write():
            posting = JobPosting(resume_id=resume_id, **data.model_dump())
            seen: set[str] = set()
            for kw in keywords:
                label = kw.term[:60]
                if label.lower() in seen:
                    continue
                seen.add(label.lower())
                posting.keywords.append(JobKeyword(
                    keyword=label, weight=kw.weight, found_in_cv=found_in_cv(kw, cv_text, catalog)
                ))  # fmt: skip
            self.session.add(posting)
            self.session.flush()
        return self._result(posting, catalog)

    def match(self, posting_id: int) -> MatchResultOut:
        """Recompute ``found_in_cv`` against the current CV and persist it."""
        posting = self.get_posting(posting_id)
        cv_text = self.cv_text(posting.resume_id)
        catalog = self.catalog()
        with self._write():
            for row in posting.keywords:
                row.found_in_cv = found_in_cv(row.keyword, cv_text, catalog)
            self.session.flush()
        return self._result(posting, catalog)

    def _result(self, posting: JobPosting, catalog: TechCatalog) -> MatchResultOut:
        rows = sorted(posting.keywords, key=lambda k: (-k.weight, k.keyword))
        out = [
            KeywordOut(
                keyword=k.keyword,
                weight=k.weight,
                found_in_cv=k.found_in_cv,
                technology=k.keyword in catalog.aliases,
            )
            for k in rows
        ]
        present = [k for k in out if k.found_in_cv]
        return MatchResultOut(
            posting=PostingOut.model_validate(posting),
            present=present,
            missing=[k for k in out if not k.found_in_cv],
            coverage=round(len(present) / len(out), 4) if out else 0.0,
        )


__all__ = ["Keyword", "MatchService"]
