"""Keyword extraction and CV matching for a job posting (spec §12). Pure functions."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

_ES = """a aca ahi al algo algun alguna algunas alguno algunos alla alli ante antes aquel aquella
aquellas aquello aquellos aqui asi aun aunque bajo bien cada casi como con contra cual cuales
cualquier cuando cuanto de del desde donde dos durante e el ella ellas ello ellos en entre era
eran es esa esas ese eso esos esta estaba estado estan estar estas este esto estos fue fueron ha
haber habia han hasta hay la las le les lo los mas me mi mis mucho muy nada ni no nos nosotros o
otra otras otro otros para pero poco por porque que quien quienes se ser si sin sino sobre son su
sus tambien tanto te tener tiene tienen todo todos tu tus un una unas uno unos usted ustedes ya y
yo sera seran puede pueden debe deben mismo misma nuevo nueva nuevos nuevas cada vez segun tales
tal etc incluyendo"""
# Words that appear in almost every posting and carry no skill information.
_FILLER = """experiencia experience anos ano years year minimo minima al menos least conocimiento
conocimientos knowledge manejo requisitos requisito requirements required deseable deseables
preferred plus buscamos busca looking seeking empresa company compania cargo rol role perfil
funciones responsabilidades responsibilities ofrecemos offer salario salary contrato contract
beneficios benefits vacante vacancy candidato candidata candidate oferta job trabajar work working
nivel level buen buena excelente strong ability capacidad habilidades skills persona personas
equipo team we you our your will must"""
STOPWORDS: frozenset[str] = frozenset(
    set(_ES.split()) | set(_FILLER.split()) | set(ENGLISH_STOP_WORDS)
)
TECH_BOOST = 2.0
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./\-]*[a-z0-9+#]|[a-z0-9]")


def normalize(text: str) -> str:
    """Lowercase without accents (keeps + # . / - inside tokens)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def tokens(text: str) -> list[str]:
    return [t.strip("./-") for t in TOKEN_RE.findall(normalize(text)) if t.strip("./-")]


def _keep(token: str) -> bool:
    return len(token) >= 2 and token not in STOPWORDS and not token.replace(".", "").isdigit()


def analyzer(text: str) -> list[str]:
    """Unigrams + bigrams of adjacent non-stopword tokens."""
    toks = tokens(text)
    unigrams = [t for t in toks if _keep(t)]
    bigrams = [f"{a} {b}" for a, b in pairwise(toks) if _keep(a) and _keep(b)]
    return unigrams + bigrams


def padded(text: str) -> str:
    """Token stream with spaces, for whole-phrase ``in`` checks."""
    return f" {' '.join(tokens(text))} "


def html_to_text(markup: str) -> str:
    markup = re.sub(r"<(style|script|head)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup)).split())


@dataclass(frozen=True)
class Keyword:
    term: str  # display form (technology canonical name or normalized term)
    weight: float
    technology: bool


class TechCatalog:
    """Technology names/aliases → canonical, for detection and matching."""

    def __init__(self, names: Mapping[str, str]) -> None:
        # names: any spelling (name or canonical) → canonical
        self.canonical_of: dict[str, str] = {}
        self.aliases: dict[str, set[str]] = {}
        for name, canonical in names.items():
            phrase = " ".join(tokens(name))
            if not phrase:
                continue
            self.canonical_of[phrase] = canonical
            self.aliases.setdefault(canonical, set()).add(phrase)
            self.aliases[canonical].add(" ".join(tokens(canonical)))

    def mentioned(self, canonical: str, text: str, padded_text: str) -> bool:
        """Case-sensitive for short or all-caps names ("Go", "R", "REST") to avoid noise."""
        if len(canonical) <= 2 or (canonical.isupper() and len(canonical) <= 5):
            return re.search(rf"(?<![\w.]){re.escape(canonical)}(?![\w+#])", text) is not None
        return any(f" {alias} " in padded_text for alias in self.aliases.get(canonical, ()))

    def in_text(self, canonical: str, text: str) -> bool:
        return self.mentioned(canonical, text, padded(text))


def extract_keywords(
    posting: str, cv_text: str, catalog: TechCatalog, top_n: int = 40
) -> list[Keyword]:
    """Top terms and bigrams of the posting by TF-IDF over [posting, cv]; technologies first."""
    vectorizer = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
    matrix = vectorizer.fit_transform([posting, cv_text or " "])
    weights = matrix[0].toarray()[0]
    scores = {
        str(term): float(w)
        for term, w in zip(vectorizer.get_feature_names_out(), weights, strict=True)
        if w > 0
    }
    base = max(scores.values(), default=1.0)
    candidates: dict[str, Keyword] = {}
    posting_padded = padded(posting)
    for canonical in catalog.aliases:
        if catalog.mentioned(canonical, posting, posting_padded):
            weight = max((scores.get(a, 0.0) for a in catalog.aliases[canonical]), default=0.0)
            candidates[canonical.lower()] = Keyword(
                canonical, round((weight or base / 2) * TECH_BOOST, 4), True
            )
    covered = {a for c in candidates.values() for a in catalog.aliases.get(c.term, ())}
    for term, weight in scores.items():
        if term in covered or term in catalog.canonical_of:
            continue
        candidates.setdefault(term, Keyword(term, round(weight, 4), False))
    ranked = sorted(candidates.values(), key=lambda k: (-k.weight, k.term))
    return ranked[:top_n]


def found_in_cv(keyword: Keyword | str, cv_text: str, catalog: TechCatalog) -> bool:
    term = keyword.term if isinstance(keyword, Keyword) else keyword
    if term in catalog.aliases:
        return catalog.in_text(term, cv_text)
    return f" {' '.join(tokens(term))} " in padded(cv_text)
