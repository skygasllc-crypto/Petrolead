"""Orchestrates a discovery job: search → extract → score → dedup → persist.

Kept as plain synchronous-friendly functions operating on a SQLAlchemy
`Session` so this can run inside a FastAPI BackgroundTask today and be
lifted into a Celery task later with minimal changes (see roadmap —
Phase 1 explicitly avoids depending on Celery/Redis being present).
"""

from __future__ import annotations

import logging

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Company,
    CompanyContact,
    CompanyEmail,
    CompanyPhone,
    CompanySource,
    LeadScore,
    SearchQuery,
    SearchStatus,
    SocialProfile,
    utcnow,
)
from app.discovery.deduplicator import find_match, is_confident_match
from app.discovery.lead_scoring import compute_lead_score
from app.discovery.normalizer import extract_domain, normalize_company_name
from app.discovery.relevance import score_relevance
from app.discovery.sources import SearchSource
from app.discovery.types import DiscoveredCompany, DiscoveryRequest
from app.schemas import DiscoverRequestSchema

logger = logging.getLogger("petrolead.services.company")


def _to_discovery_request(payload: DiscoverRequestSchema) -> DiscoveryRequest:
    return DiscoveryRequest(
        region=payload.region,
        country=payload.country,
        city=payload.city,
        industry=payload.industry,
        activity=payload.activity,
        products=list(payload.products),
        keywords=list(payload.keywords),
        limit=payload.limit,
    )


def _union(a: list[str], b: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in (*a, *b):
        if item and item not in seen:
            seen[item] = None
    return list(seen.keys())


def _apply_relevance(company: Company) -> None:
    result = score_relevance(
        company_name=company.company_name,
        description=company.description,
        activities=company.activities,
        products=company.products,
        keywords=company.keywords,
        industry=company.industry,
    )
    company.relevance_score = result.score


def _apply_contact_info(db: Session, company: Company, candidate: DiscoveredCompany) -> None:
    """Fill in the contact page + any newly-seen social profiles (Phase 2).

    Idempotent: re-running discovery on an already-known company only adds
    what's missing, never overwrites a contact page already on file, and
    never inserts a duplicate (platform, url) social profile row.
    """
    if candidate.contact_page_url:
        if company.contact is None:
            company.contact = CompanyContact(contact_page_url=candidate.contact_page_url)
        elif not company.contact.contact_page_url:
            company.contact.contact_page_url = candidate.contact_page_url

    existing_platforms = {p.platform for p in company.social_profiles}
    for profile in candidate.social_profiles:
        platform = profile.get("platform")
        url = profile.get("url")
        if not platform or not url or platform in existing_platforms:
            continue
        company.social_profiles.append(SocialProfile(platform=platform, url=url))
        existing_platforms.add(platform)


def _apply_email_phone_info(company: Company, candidate: DiscoveredCompany) -> None:
    """Persist newly-seen emails/phones (Phase 3/4). Idempotent per company."""
    existing_emails = {e.email.lower() for e in company.emails}
    for entry in candidate.emails:
        email = entry.get("email")
        if not email or email.lower() in existing_emails:
            continue
        company.emails.append(CompanyEmail(email=email, is_valid=entry.get("is_valid")))
        existing_emails.add(email.lower())

    existing_phones = {p.phone for p in company.phones}
    for entry in candidate.phones:
        phone = entry.get("phone")
        if not phone or phone in existing_phones:
            continue
        company.phones.append(CompanyPhone(phone=phone, is_valid=bool(entry.get("is_valid"))))
        existing_phones.add(phone)


def _apply_lead_score(company: Company) -> None:
    """Recompute the composite lead score (Phase 7) from current company state."""
    result = compute_lead_score(
        relevance_score=company.relevance_score,
        has_website=bool(company.website),
        has_contact_page=bool(company.contact and company.contact.contact_page_url),
        has_social_profile=len(company.social_profiles) > 0,
        has_verified_email=any(e.is_valid for e in company.emails),
        has_verified_phone=any(p.is_valid for p in company.phones),
    )
    if company.lead_score is None:
        company.lead_score = LeadScore(score=result.score)
    else:
        company.lead_score.score = result.score
    company.lead_score.relevance_component = result.relevance_component
    company.lead_score.contact_completeness_component = result.contact_completeness_component
    company.lead_score.verified_email_component = result.verified_email_component
    company.lead_score.verified_phone_component = result.verified_phone_component


def _create_company(db: Session, candidate: DiscoveredCompany) -> Company:
    company = Company(
        company_name=candidate.company_name,
        normalized_name=normalize_company_name(candidate.company_name),
        country=candidate.country,
        city=candidate.city,
        region=candidate.region,
        website=candidate.website,
        domain=extract_domain(candidate.website),
        industry=candidate.industry,
        description=candidate.description,
        activities=candidate.activities,
        products=candidate.products,
        keywords=candidate.keywords,
        source=candidate.source,
        source_url=candidate.source_url,
    )
    _apply_relevance(company)
    db.add(company)
    db.flush()  # assign company.id before creating the FK'd source row
    db.add(
        CompanySource(
            company_id=company.id,
            source=candidate.source,
            source_url=candidate.source_url,
            raw_company_name=candidate.company_name,
            match_confidence=1.0,
        )
    )
    _apply_contact_info(db, company, candidate)
    _apply_email_phone_info(company, candidate)
    _apply_lead_score(company)
    return company


def _merge_into_company(
    db: Session, existing: Company, candidate: DiscoveredCompany, confidence: float
) -> None:
    if not existing.website and candidate.website:
        existing.website = candidate.website
        existing.domain = extract_domain(candidate.website)
    if not existing.description and candidate.description:
        existing.description = candidate.description
    if not existing.industry and candidate.industry:
        existing.industry = candidate.industry
    if not existing.country and candidate.country:
        existing.country = candidate.country
    if not existing.city and candidate.city:
        existing.city = candidate.city
    if not existing.region and candidate.region:
        existing.region = candidate.region

    existing.activities = _union(existing.activities, candidate.activities)
    existing.products = _union(existing.products, candidate.products)
    existing.keywords = _union(existing.keywords, candidate.keywords)
    _apply_relevance(existing)
    _apply_contact_info(db, existing, candidate)
    _apply_email_phone_info(existing, candidate)
    _apply_lead_score(existing)

    db.add(
        CompanySource(
            company_id=existing.id,
            source=candidate.source,
            source_url=candidate.source_url,
            raw_company_name=candidate.company_name,
            match_confidence=confidence,
        )
    )
    logger.info(
        "Deduplication: merged candidate %r into existing company %r (confidence=%.2f)",
        candidate.company_name,
        existing.company_name,
        confidence,
    )


async def run_discovery(db: Session, payload: DiscoverRequestSchema) -> SearchQuery:
    """Execute a full discovery job synchronously and persist the results."""
    search_query = SearchQuery(
        region=payload.region,
        country=payload.country,
        city=payload.city,
        industry=payload.industry,
        activity=payload.activity,
        products=payload.products,
        keywords=payload.keywords,
        result_limit=payload.limit,
        status=SearchStatus.RUNNING,
    )
    db.add(search_query)
    db.commit()
    db.refresh(search_query)

    logger.info(
        "Search %s started: region=%s country=%s city=%s industry=%s products=%s keywords=%s",
        search_query.id,
        payload.region,
        payload.country,
        payload.city,
        payload.industry,
        payload.products,
        payload.keywords,
    )

    discovery_request = _to_discovery_request(payload)
    source = SearchSource()

    try:
        candidates = await source.discover(discovery_request)
    except Exception as exc:  # noqa: BLE001 — a failed job must not crash the API
        logger.exception("Search %s failed during discovery", search_query.id)
        search_query.status = SearchStatus.FAILED
        search_query.error = str(exc)
        search_query.status_message = "Discovery failed. See server logs for details."
        search_query.completed_at = utcnow()
        db.commit()
        db.refresh(search_query)
        return search_query

    logger.info(
        "Search %s: %d candidate(s) discovered, deduplicating", search_query.id, len(candidates)
    )

    new_count = 0
    duplicate_count = 0
    result_companies: list[Company] = []

    for candidate in candidates:
        if not candidate.company_name or not candidate.company_name.strip():
            continue
        try:
            match = find_match(db, candidate)
            if is_confident_match(match):
                _merge_into_company(db, match.company, candidate, match.confidence)
                duplicate_count += 1
                result_companies.append(match.company)
            else:
                company = _create_company(db, candidate)
                new_count += 1
                result_companies.append(company)
        except Exception:
            logger.exception(
                "Search %s: failed to persist candidate %r — skipping",
                search_query.id,
                candidate.company_name,
            )
            db.rollback()
            continue

    search_query.status = SearchStatus.COMPLETED
    search_query.result_count = len(candidates)
    search_query.new_company_count = new_count
    search_query.duplicate_count = duplicate_count
    search_query.status_message = (
        f"Found {len(candidates)} result(s): {new_count} new, {duplicate_count} matched existing."
    )
    search_query.completed_at = utcnow()
    db.commit()
    db.refresh(search_query)

    # Transient (non-mapped) attribute so the API layer can render the
    # companies produced by this job without a dedicated join table.
    search_query.result_companies = result_companies
    logger.info(
        "Search %s completed: new=%d duplicates=%d total=%d",
        search_query.id,
        new_count,
        duplicate_count,
        len(candidates),
    )
    return search_query


def _filtered_companies_stmt(
    *,
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = None,
    min_lead_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    search: str | None = None,
):
    """Shared WHERE-clause builder for `list_companies` and `export_companies`.

    Kept in one place (Phase 9: advanced search & filtering) so pagination
    and export always agree on what "matches the filters" means.
    """
    stmt = select(Company)
    if country:
        stmt = stmt.where(Company.country == country)
    if region:
        stmt = stmt.where(Company.region == region)
    if industry:
        stmt = stmt.where(Company.industry == industry)
    if product:
        # Products are stored as a JSON list; a substring match on the
        # serialized column is portable across SQLite and Postgres, unlike
        # JSON-array "contains" operators (which aren't dialect-uniform).
        stmt = stmt.where(cast(Company.products, String).like(f'%"{product}"%'))
    if min_relevance is not None:
        stmt = stmt.where(Company.relevance_score >= min_relevance)
    if min_lead_score is not None:
        stmt = stmt.where(Company.lead_score.has(LeadScore.score >= min_lead_score))
    if has_email is True:
        stmt = stmt.where(Company.emails.any())
    elif has_email is False:
        stmt = stmt.where(~Company.emails.any())
    if has_phone is True:
        stmt = stmt.where(Company.phones.any())
    elif has_phone is False:
        stmt = stmt.where(~Company.phones.any())
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(Company.normalized_name.like(like))
    return stmt


def list_companies(
    db: Session,
    *,
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = None,
    min_lead_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Company], int]:
    stmt = _filtered_companies_stmt(
        country=country,
        region=region,
        industry=industry,
        product=product,
        min_relevance=min_relevance,
        min_lead_score=min_lead_score,
        has_email=has_email,
        has_phone=has_phone,
        search=search,
    )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = (
        stmt.order_by(Company.relevance_score.desc(), Company.discovered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


# Hard ceiling on a single export so an unbounded filter can't return the
# entire table in one response.
MAX_EXPORT_ROWS = 5000


def export_companies(
    db: Session,
    *,
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = None,
    min_lead_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    search: str | None = None,
) -> list[Company]:
    """Return every company matching the filters, unpaginated (Phase 8: export)."""
    stmt = _filtered_companies_stmt(
        country=country,
        region=region,
        industry=industry,
        product=product,
        min_relevance=min_relevance,
        min_lead_score=min_lead_score,
        has_email=has_email,
        has_phone=has_phone,
        search=search,
    ).order_by(Company.relevance_score.desc(), Company.discovered_at.desc())
    stmt = stmt.limit(MAX_EXPORT_ROWS)
    return list(db.execute(stmt).scalars().all())


def to_export_rows(companies: list[Company]) -> list[dict]:
    """Flatten companies into export rows (Phase 8: CSV/Excel export)."""
    rows = []
    for c in companies:
        rows.append(
            {
                "Company Name": c.company_name,
                "Country": c.country or "",
                "City": c.city or "",
                "Region": c.region or "",
                "Industry": c.industry or "",
                "Petroleum Activities": ", ".join(c.activities),
                "Products": ", ".join(c.products),
                "Website": c.website or "",
                "Contact Page": c.contact.contact_page_url if c.contact else "",
                "Social Profiles": ", ".join(f"{p.platform}: {p.url}" for p in c.social_profiles),
                "Emails": ", ".join(e.email for e in c.emails),
                "Phones": ", ".join(p.phone for p in c.phones),
                "Source": c.source or "",
                "Relevance Score": c.relevance_score,
                "Lead Score": c.lead_score.score if c.lead_score else "",
                "Discovery Date": c.discovered_at.isoformat(),
            }
        )
    return rows


def get_company(db: Session, company_id: str) -> Company | None:
    return db.get(Company, company_id)


def list_searches(
    db: Session, *, page: int = 1, page_size: int = 25
) -> tuple[list[SearchQuery], int]:
    stmt = select(SearchQuery)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = (
        stmt.order_by(SearchQuery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total
