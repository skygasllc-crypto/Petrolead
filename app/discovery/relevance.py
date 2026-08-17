"""Petroleum-industry relevance scoring.

Scores a candidate company's text (name + description + activities +
products + keywords) against curated petroleum-industry vocabularies.
Deliberately simple and modular — later phases can swap this for an
ML-based classifier without changing the interface (`score_relevance`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Vocabularies -----------------------------------------------------------
# Term -> weight. Weight reflects how strong a signal the term is for
# "this is a real petroleum/oil & gas industry business".

TRADING_TERMS: dict[str, int] = {
    "petroleum trading": 25,
    "oil trading": 25,
    "fuel trading": 25,
    "energy trading": 18,
    "petroleum products": 20,
    "oil products": 18,
    "fuel supplier": 20,
    "petroleum supplier": 20,
    "oil supplier": 18,
    "fuel distributor": 18,
    "petroleum distributor": 18,
    "oil & gas": 20,
    "oil and gas": 20,
}

PRODUCT_TERMS: dict[str, int] = {
    "en590": 25,
    "diesel": 15,
    "jet a1": 22,
    "jet a-1": 22,
    "aviation fuel": 20,
    "fuel oil": 18,
    "gasoil": 18,
    "gas oil": 18,
    "crude oil": 20,
    "lpg": 18,
    "lng": 18,
    "bitumen": 18,
    "petroleum coke": 18,
    "petcoke": 18,
    "gasoline": 15,
    "petrol": 12,
    "naphtha": 18,
    "mazut": 15,
    "kerosene": 15,
}

INFRASTRUCTURE_TERMS: dict[str, int] = {
    "refinery": 22,
    "terminal": 10,
    "tank storage": 22,
    "tank farm": 22,
    "bunkering": 22,
    "bunker fuel": 20,
    "bunker supplier": 20,
    "petroleum storage": 20,
    "oil terminal": 20,
    "storage tank": 14,
    "pipeline": 12,
    "jetty": 10,
    "petrochemical": 15,
}

GENERIC_PETROLEUM_TERMS: dict[str, int] = {
    "petroleum": 15,
    "oil company": 12,
    "energy company": 8,
    "hydrocarbon": 12,
    "fuel": 6,
    "downstream": 8,
    "upstream": 8,
    "midstream": 8,
}

_ALL_VOCAB: dict[str, int] = {
    **TRADING_TERMS,
    **PRODUCT_TERMS,
    **INFRASTRUCTURE_TERMS,
    **GENERIC_PETROLEUM_TERMS,
}

# Terms that strongly suggest the "petroleum" match is incidental/unrelated
# (e.g. a jelly/cosmetics company mentioning "petroleum jelly").
NEGATIVE_TERMS: dict[str, int] = {
    "petroleum jelly": 30,
    "vaseline": 15,
}


@dataclass
class RelevanceResult:
    score: int
    tier: str
    matched_terms: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"score": self.score, "tier": self.tier, "matched_terms": self.matched_terms}


def _tier_for(score: int) -> str:
    if score >= 80:
        return "Highly Relevant"
    if score >= 60:
        return "Relevant"
    if score >= 30:
        return "Possible"
    return "Low"


def _build_corpus(
    *,
    company_name: str = "",
    description: str = "",
    activities: list[str] | None = None,
    products: list[str] | None = None,
    keywords: list[str] | None = None,
    industry: str = "",
) -> str:
    parts = [
        company_name or "",
        description or "",
        industry or "",
        " ".join(activities or []),
        " ".join(products or []),
        " ".join(keywords or []),
    ]
    return " ".join(parts).lower()


def score_relevance(
    *,
    company_name: str = "",
    description: str = "",
    activities: list[str] | None = None,
    products: list[str] | None = None,
    keywords: list[str] | None = None,
    industry: str = "",
) -> RelevanceResult:
    """Compute a 0-100 petroleum-industry relevance score for a candidate company."""
    corpus = _build_corpus(
        company_name=company_name,
        description=description,
        activities=activities,
        products=products,
        keywords=keywords,
        industry=industry,
    )

    if not corpus.strip():
        return RelevanceResult(score=0, tier=_tier_for(0), matched_terms=[])

    raw_score = 0
    matched: list[str] = []

    for term, weight in _ALL_VOCAB.items():
        if _term_present(term, corpus):
            raw_score += weight
            matched.append(term)

    for term, penalty in NEGATIVE_TERMS.items():
        if _term_present(term, corpus):
            raw_score -= penalty

    score = max(0, min(100, raw_score))
    return RelevanceResult(score=score, tier=_tier_for(score), matched_terms=sorted(matched))


def _term_present(term: str, corpus: str) -> bool:
    if " " in term or "-" in term:
        return term in corpus
    return re.search(rf"\b{re.escape(term)}\b", corpus) is not None
