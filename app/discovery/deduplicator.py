"""Company deduplication.

Multiple sources will often surface the "same" company under slightly
different names, URLs, or listing pages. This module decides whether a
newly discovered candidate is actually an existing `Company` row, using
several matching signals, and only merges when confident. When
confidence is low, records are deliberately kept separate rather than
risking an incorrect merge.

Matching signals, in order of trust:
    1. Exact domain match (very high confidence — same website == same company)
    2. Exact normalized-name match + compatible location
    3. Fuzzy normalized-name similarity + compatible location
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.database.models import Company
from app.discovery.normalizer import extract_domain, normalize_company_name
from app.discovery.types import DiscoveredCompany

# Below this, we never merge — treat as a distinct company.
MERGE_CONFIDENCE_THRESHOLD = 0.85

DOMAIN_MATCH_CONFIDENCE = 0.98
EXACT_NAME_MATCH_CONFIDENCE = 0.95
FUZZY_NAME_SIMILARITY_THRESHOLD = 0.90


@dataclass
class MatchResult:
    company: Company | None
    confidence: float


def _locations_compatible(a_country: str | None, a_city: str | None, company: Company) -> bool:
    """True if location data doesn't actively contradict a potential match.

    Missing location data on either side is treated as "not contradictory"
    (we don't have enough information to rule it out) rather than as a
    mismatch — that keeps the matcher conservative in the direction of
    avoiding false negatives on the confidence checks that already
    require a strong name/domain signal.
    """
    if (
        a_country
        and company.country
        and a_country.strip().lower() != company.country.strip().lower()
    ):
        return False
    if a_city and company.city and a_city.strip().lower() != company.city.strip().lower():
        return False
    return True


def find_match(db: Session, candidate: DiscoveredCompany, owner_id: str) -> MatchResult:
    """Find the best match for a discovered candidate among one account's
    saved companies, if any.

    Scoped to `owner_id`: every account's companies are private to it, so
    two customers saving the same company each get their own record."""
    domain = extract_domain(candidate.website)
    normalized = normalize_company_name(candidate.company_name)
    owned = db.query(Company).filter(Company.owner_id == owner_id)

    if domain:
        existing = owned.filter(Company.domain == domain).first()
        if existing:
            return MatchResult(company=existing, confidence=DOMAIN_MATCH_CONFIDENCE)

    if not normalized:
        return MatchResult(company=None, confidence=0.0)

    exact_matches = owned.filter(Company.normalized_name == normalized).all()
    compatible_exact = [
        c for c in exact_matches if _locations_compatible(candidate.country, candidate.city, c)
    ]
    if compatible_exact:
        return MatchResult(company=compatible_exact[0], confidence=EXACT_NAME_MATCH_CONFIDENCE)
    if exact_matches:
        # Same name but locations actively conflict — too risky to auto-merge.
        return MatchResult(company=None, confidence=0.5)

    best_company: Company | None = None
    best_similarity = 0.0
    country_scope = (
        owned.filter(Company.country == candidate.country).all() if candidate.country else []
    )
    for company in country_scope:
        similarity = SequenceMatcher(None, normalized, company.normalized_name).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_company = company

    if best_company and best_similarity >= FUZZY_NAME_SIMILARITY_THRESHOLD:
        return MatchResult(company=best_company, confidence=best_similarity)

    return MatchResult(company=None, confidence=best_similarity)


def is_confident_match(match: MatchResult) -> bool:
    return match.company is not None and match.confidence >= MERGE_CONFIDENCE_THRESHOLD
