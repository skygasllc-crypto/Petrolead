"""Orchestrates a discovery job: search → extract → score → dedup → persist.

Kept as plain synchronous-friendly functions operating on a SQLAlchemy
`Session` so this can run inside a FastAPI BackgroundTask today and be
lifted into a Celery task later with minimal changes (see roadmap —
Phase 1 explicitly avoids depending on Celery/Redis being present).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
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
from app.discovery.email_finder import find_person_email
from app.discovery.lead_scoring import compute_lead_score
from app.discovery.normalizer import extract_domain, normalize_company_name
from app.discovery.profile_lookup import (
    build_profile_snippet_query,
    detect_personal_profile_platform,
    parse_profile_snippet,
)
from app.discovery.relevance import score_relevance
from app.discovery.search import (
    B2B_DIRECTORY_DOMAINS,
    SearchQuotaExceededError,
    get_search_provider,
)
from app.discovery.sources import B2BSource, SearchSource, SocialSource, WebsiteSource
from app.discovery.types import DiscoveredCompany, DiscoveryRequest
from app.schemas import DiscoverRequestSchema

logger = logging.getLogger("petrolead.services.company")


class UrlLookupError(Exception):
    """Raised when a pasted URL couldn't be fetched or yielded nothing usable."""


class CompanySaveError(Exception):
    """Raised when a previewed candidate couldn't be persisted."""


def _to_discovery_request(payload: DiscoverRequestSchema) -> DiscoveryRequest:
    return DiscoveryRequest(
        region=payload.region,
        country=payload.country,
        city=payload.city,
        industry=payload.industry,
        activity=payload.activity,
        role=payload.role,
        products=list(payload.products),
        keywords=list(payload.keywords),
        limit=payload.limit,
        include_social_search=payload.include_social_search,
        include_b2b_directories=payload.include_b2b_directories,
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

    if candidate.contact_person_name:
        if company.contact is None:
            company.contact = CompanyContact(
                contact_person_name=candidate.contact_person_name,
                contact_person_title=candidate.contact_person_title,
            )
        elif not company.contact.contact_person_name:
            company.contact.contact_person_name = candidate.contact_person_name
            company.contact.contact_person_title = candidate.contact_person_title

    existing_platforms = {p.platform for p in company.social_profiles}
    for profile in candidate.social_profiles:
        platform = profile.get("platform")
        url = profile.get("url")
        if not platform or not url or platform in existing_platforms:
            continue
        company.social_profiles.append(SocialProfile(platform=platform, url=url))
        existing_platforms.add(platform)


def _apply_email_phone_info(company: Company, candidate: DiscoveredCompany) -> None:
    """Persist newly-seen emails/phones (Phase 3/4).

    Emails are finalized on first extraction: once a company has at least
    one email on file, later discovery runs that re-match this company
    never touch its emails again — not re-added, not re-validated, not
    replaced. This keeps a company's email list stable across repeat
    searches instead of re-extracting (and potentially flip-flopping
    validity) every time the same company is rediscovered. Phones aren't
    finalized this way; they still accumulate newly-seen numbers.
    """
    if not company.emails:
        existing_emails: set[str] = set()
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


def _create_company(db: Session, candidate: DiscoveredCompany, owner_id: str) -> Company:
    company = Company(
        owner_id=owner_id,
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


def _persist_candidate(
    db: Session, candidate: DiscoveredCompany, *, owner_id: str, context: str
) -> tuple[Company | None, bool]:
    """Dedup + create-or-merge one candidate into `owner_id`'s companies.
    Returns (company, is_new).

    Returns (None, False) if the candidate was unusable (no name) or
    persistence failed — callers just skip it, same as any other
    single-candidate failure never aborting the whole job. Runs inside a
    SAVEPOINT (`db.begin_nested()`) so that a failed candidate only rolls
    back its own work — not the still-uncommitted inserts of earlier
    candidates already persisted in the same batch loop (`run_discovery`,
    `save_candidates_bulk`), which share one session and one final commit.
    """
    if not candidate.company_name or not candidate.company_name.strip():
        return None, False
    try:
        with db.begin_nested():
            match = find_match(db, candidate, owner_id)
            if is_confident_match(match):
                _merge_into_company(db, match.company, candidate, match.confidence)
                company, is_new = match.company, False
            else:
                company, is_new = _create_company(db, candidate, owner_id), True
        return company, is_new
    except Exception:
        logger.exception(
            "%s: failed to persist candidate %r — skipping", context, candidate.company_name
        )
        return None, False


def _score_candidate(candidate: DiscoveredCompany) -> tuple[int, int]:
    """Relevance + lead score for a not-yet-saved candidate (preview only).

    Mirrors `_apply_relevance`/`_apply_lead_score`, just computed off the
    transient `DiscoveredCompany` instead of a persisted `Company` row —
    nothing here touches the database.
    """
    relevance = score_relevance(
        company_name=candidate.company_name,
        description=candidate.description,
        activities=candidate.activities,
        products=candidate.products,
        keywords=candidate.keywords,
        industry=candidate.industry,
    )
    lead = compute_lead_score(
        relevance_score=relevance.score,
        has_website=bool(candidate.website),
        has_contact_page=bool(candidate.contact_page_url),
        has_social_profile=len(candidate.social_profiles) > 0,
        has_verified_email=any(e.get("is_valid") for e in candidate.emails),
        has_verified_phone=any(p.get("is_valid") for p in candidate.phones),
    )
    return relevance.score, lead.score


def _merge_candidates_in_memory(candidates: list[DiscoveredCompany]) -> list[DiscoveredCompany]:
    """Collapse obvious duplicate candidates within one preview batch.

    Preview mode never touches the database, so `find_match` (which only
    matches against already-saved companies) can't catch two candidates
    in the *same* batch describing the same company — e.g. the base web
    search and the B2B/social connectors both surfacing "ABC Petroleum".
    This applies the same domain/name+location matching signals purely
    in memory, merging their data the same way `_merge_into_company`
    would on save, so a preview doesn't show obvious duplicate rows.
    """
    merged: list[DiscoveredCompany] = []
    domain_index: dict[str, int] = {}
    name_location_index: dict[tuple[str, str | None], int] = {}

    for candidate in candidates:
        if not candidate.company_name or not candidate.company_name.strip():
            continue

        domain = extract_domain(candidate.website)
        normalized = normalize_company_name(candidate.company_name)
        location_key = (normalized, (candidate.country or "").strip().lower() or None)

        target_idx = domain_index.get(domain) if domain else None
        if target_idx is None:
            target_idx = name_location_index.get(location_key)

        if target_idx is not None:
            existing = merged[target_idx]
            existing.activities = _union(existing.activities, candidate.activities)
            existing.products = _union(existing.products, candidate.products)
            existing.keywords = _union(existing.keywords, candidate.keywords)
            if not existing.website and candidate.website:
                existing.website = candidate.website
            if not existing.description and candidate.description:
                existing.description = candidate.description
            if not existing.contact_page_url and candidate.contact_page_url:
                existing.contact_page_url = candidate.contact_page_url

            seen_platforms = {p["platform"] for p in existing.social_profiles}
            existing.social_profiles += [
                p for p in candidate.social_profiles if p["platform"] not in seen_platforms
            ]
            seen_emails = {e["email"].lower() for e in existing.emails if e.get("email")}
            existing.emails += [
                e
                for e in candidate.emails
                if e.get("email") and e["email"].lower() not in seen_emails
            ]
            seen_phones = {p["phone"] for p in existing.phones if p.get("phone")}
            existing.phones += [
                p for p in candidate.phones if p.get("phone") and p["phone"] not in seen_phones
            ]
            continue

        idx = len(merged)
        merged.append(candidate)
        if domain:
            domain_index[domain] = idx
        name_location_index[location_key] = idx

    return merged


def _build_preview(db: Session, candidate: DiscoveredCompany, owner_id: str) -> dict:
    """Score a candidate and check whether it matches one of `owner_id`'s
    saved companies, without writing anything — the shape returned to the
    API for both `/discover` and `/discover-url` previews."""
    relevance_score, lead_score = _score_candidate(candidate)
    match = find_match(db, candidate, owner_id)
    already_saved = is_confident_match(match)

    return {
        "company_name": candidate.company_name,
        "website": candidate.website,
        "country": candidate.country,
        "city": candidate.city,
        "region": candidate.region,
        "industry": candidate.industry,
        "description": candidate.description,
        "activities": candidate.activities,
        "products": candidate.products,
        "keywords": candidate.keywords,
        "source": candidate.source,
        "source_url": candidate.source_url,
        "is_mock": candidate.is_mock,
        "contact_page_url": candidate.contact_page_url,
        "social_profiles": candidate.social_profiles,
        "emails": candidate.emails,
        "phones": candidate.phones,
        "contact_person_name": candidate.contact_person_name,
        "contact_person_title": candidate.contact_person_title,
        "relevance_score": relevance_score,
        "lead_score": lead_score,
        "already_saved": already_saved,
        "existing_company_id": match.company.id if already_saved and match.company else None,
    }


async def _execute_sources(
    db: Session, search_query: SearchQuery, payload: DiscoverRequestSchema
) -> list[DiscoveredCompany] | None:
    """Run the configured sources for one search. Returns None (and marks
    `search_query` FAILED) if the sources themselves raised — a per-source
    failure inside `SearchSource.discover()` etc. is already caught there
    and just yields fewer candidates, so reaching an exception here means
    something more fundamental broke (e.g. a misconfigured provider).

    The exception is the provider's quota running out: a source raises it
    only when it found nothing. The search fails, with the quota message
    shown to the user, only if no source returned any candidates."""
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
    sources: list[SearchSource | B2BSource | SocialSource] = [SearchSource()]
    if discovery_request.include_social_search:
        sources.append(SocialSource())
    if discovery_request.include_b2b_directories:
        sources.append(B2BSource())

    try:
        batches = await asyncio.gather(
            *(s.discover(discovery_request) for s in sources), return_exceptions=True
        )
        candidates: list[DiscoveredCompany] = []
        quota_errors: list[SearchQuotaExceededError] = []
        for batch in batches:
            if isinstance(batch, SearchQuotaExceededError):
                quota_errors.append(batch)
            elif isinstance(batch, BaseException):
                raise batch
            else:
                candidates.extend(batch)
        if quota_errors and not candidates:
            raise quota_errors[0]
        return candidates
    except Exception as exc:  # noqa: BLE001 — a failed job must not crash the API
        if isinstance(exc, SearchQuotaExceededError):
            logger.warning("Search %s failed: %s", search_query.id, exc)
            status_message = str(exc)
        else:
            logger.exception("Search %s failed during discovery", search_query.id)
            status_message = "Discovery failed. See server logs for details."
        search_query.status = SearchStatus.FAILED
        search_query.error = str(exc)
        search_query.status_message = status_message
        search_query.completed_at = utcnow()
        db.commit()
        db.refresh(search_query)
        return None


def _new_search_query(payload: DiscoverRequestSchema, owner_id: str) -> SearchQuery:
    return SearchQuery(
        owner_id=owner_id,
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


async def discover_preview(
    db: Session, payload: DiscoverRequestSchema, owner_id: str
) -> tuple[SearchQuery, list[dict]]:
    """Run a discovery search WITHOUT saving anything (the interactive
    Discover page / paste-a-link flow) — the user reviews results and
    explicitly saves the ones they want via `save_candidate`.

    `SearchQuery.new_company_count`/`duplicate_count` here mean "would be
    new" / "already in your saved companies" at preview time, not actual
    save outcomes — saving can still change since the database can move
    between preview and save.
    """
    search_query = _new_search_query(payload, owner_id)
    db.add(search_query)
    db.commit()
    db.refresh(search_query)

    candidates = await _execute_sources(db, search_query, payload)
    if candidates is None:
        return search_query, []

    candidates = _merge_candidates_in_memory(candidates)
    logger.info("Search %s: %d candidate(s) previewed, not saved", search_query.id, len(candidates))

    previews = [_build_preview(db, c, owner_id) for c in candidates if c.company_name.strip()]
    new_count = sum(1 for p in previews if not p["already_saved"])
    duplicate_count = len(previews) - new_count

    search_query.status = SearchStatus.COMPLETED
    search_query.result_count = len(previews)
    search_query.new_company_count = new_count
    search_query.duplicate_count = duplicate_count
    search_query.status_message = (
        f"Found {len(previews)} result(s): {new_count} not yet saved, "
        f"{duplicate_count} already in your companies."
    )
    search_query.completed_at = utcnow()
    db.commit()
    db.refresh(search_query)

    logger.info(
        "Search %s completed: %d previewed, %d already saved",
        search_query.id,
        new_count,
        duplicate_count,
    )
    return search_query, previews


async def run_discovery(db: Session, payload: DiscoverRequestSchema, owner_id: str) -> SearchQuery:
    """Execute a full discovery job AND immediately persist the results
    into `owner_id`'s companies.

    Used only by scheduled/automated searches (Phase 10) — there's no
    user present to review and click Save on an unattended run, so those
    save straight through. Interactive discovery goes through
    `discover_preview` + `save_candidate` instead.
    """
    search_query = _new_search_query(payload, owner_id)
    db.add(search_query)
    db.commit()
    db.refresh(search_query)

    candidates = await _execute_sources(db, search_query, payload)
    if candidates is None:
        search_query.emails_found = 0
        return search_query

    logger.info(
        "Search %s: %d candidate(s) discovered, deduplicating", search_query.id, len(candidates)
    )

    new_count = 0
    duplicate_count = 0
    result_companies: list[Company] = []

    for candidate in candidates:
        company, is_new = _persist_candidate(
            db, candidate, owner_id=owner_id, context=f"Search {search_query.id}"
        )
        if company is None:
            continue
        result_companies.append(company)
        if is_new:
            new_count += 1
        else:
            duplicate_count += 1

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

    # Transient (non-mapped) attributes for the caller: the companies this
    # job produced (rendered by the API without a dedicated join table), and
    # how many came with a business email — what the run costs its owner in
    # credits (see `saved_search_service.run_saved_search`).
    search_query.result_companies = result_companies
    search_query.emails_found = sum(1 for candidate in candidates if candidate.emails)
    logger.info(
        "Search %s completed: new=%d duplicates=%d total=%d",
        search_query.id,
        new_count,
        duplicate_count,
        len(candidates),
    )
    return search_query


_NOTHING_USABLE_MESSAGE = (
    "Could not fetch this page, or it didn't publish any usable "
    "information (a name, description, contact page, or business "
    "email/phone). This is common for social-media profile URLs, "
    "which are usually login-gated — try the company's own website "
    "instead."
)


async def discover_from_url_preview(db: Session, url: str, owner_id: str) -> dict:
    """Fetch one pasted URL and preview whatever public contact info is
    there, WITHOUT saving it — same "review then save" flow as
    `discover_preview`.

    A personal profile URL (`linkedin.com/in/...`) is routed to
    `_preview_from_profile_snippet` instead — that page is login-gated, so
    it's never fetched directly. Everything else reuses `WebsiteSource`
    (Phase 1) end to end — a plain, respectful page fetch of the URL and,
    if found, its Contact page. Works well for a company's own website. A
    raw *company* social-platform URL (a LinkedIn/Facebook page, not a
    person) will usually come back empty here too: those are also
    login-gated, and this never bypasses that — see `discovery/extractor.py`.
    """
    profile_platform = detect_personal_profile_platform(url)
    if profile_platform:
        return await _preview_from_profile_snippet(
            db, url, platform=profile_platform, owner_id=owner_id
        )

    candidates = await WebsiteSource(url).discover(DiscoveryRequest())
    candidate = candidates[0]

    learned_anything = bool(
        candidate.company_name != candidate.website
        or candidate.description
        or candidate.contact_page_url
        or candidate.social_profiles
        or candidate.emails
        or candidate.phones
    )
    if not learned_anything:
        raise UrlLookupError(_NOTHING_USABLE_MESSAGE)

    preview = _build_preview(db, candidate, owner_id)
    logger.info("URL lookup %s previewed as %r (not saved)", url, candidate.company_name)
    return preview


_BLOCKED_DOMAIN_SUBSTRINGS = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    *B2B_DIRECTORY_DOMAINS,
}


async def _resolve_company_domain(provider, company_name: str) -> str | None:
    """Best-effort: the likely official website domain for a company name,
    taken only from an actual search-engine result — never guessed, and
    never a known social-platform or B2B-directory host (those aren't a
    company's own site)."""
    try:
        results = await provider.search(f'"{company_name}" official website', limit=3)
    except Exception:
        logger.warning("Domain resolution search failed for company=%r", company_name)
        return None

    for result in results:
        domain = extract_domain(result.url)
        if not domain or any(blocked in domain for blocked in _BLOCKED_DOMAIN_SUBSTRINGS):
            continue
        return domain
    return None


async def _resolve_domain_and_email(
    provider, settings, *, company_name: str, full_name: str
) -> tuple[str | None, list[dict]]:
    """Shared best-effort enrichment used by both the profile-snippet
    fallback and bulk contact lookup: resolve a company's domain via an
    actual search result, then (if `HUNTER_IO_API_KEY` is configured) ask
    Hunter.io for a confident business email for this specific person.
    Skipped entirely in mock mode — never fabricates either value."""
    if provider.name == "mock":
        return None, []
    domain = await _resolve_company_domain(provider, company_name)
    if not domain:
        return None, []
    found = await find_person_email(domain=domain, full_name=full_name, settings=settings)
    return domain, ([found] if found else [])


async def _preview_from_profile_snippet(
    db: Session, url: str, *, platform: str, owner_id: str
) -> dict:
    """Fallback for a personal social-profile URL: the page itself is
    login-gated and never fetched. Instead, ask the configured
    `SearchProvider` for whatever public snippet it has indexed for that
    exact URL (same trust model as `SocialSource`), and parse a
    name/title/company out of it if there is one.

    The person is returned even when the listing names no employer and even
    when no business email could be found: knowing who someone is and where
    their profile lives is worth showing, and a lookup that found nothing
    billable costs the customer nothing (see `api/companies.py` — credits
    are spent only on an email that was actually found). A contact without
    a company is preview-only: `companies.company_name` is NOT NULL, so it
    can't be saved until the user names an employer.

    Fails only when the profile has no usable public listing at all.
    """
    settings = get_settings()
    provider = get_search_provider(settings)
    query = build_profile_snippet_query(url)

    try:
        results = await provider.search(query, limit=3)
    except SearchQuotaExceededError as exc:
        # Not the page being login-gated: the lookup never got an answer.
        raise UrlLookupError(str(exc)) from exc
    except Exception:
        logger.warning("Profile snippet lookup failed for url=%r", url, exc_info=True)
        results = []

    # Prefer a listing that names an employer, but keep the first name-only
    # parse rather than discarding it: a contact with no company is still a
    # result, just one that can't be enriched any further.
    parsed = None
    for result in results:
        candidate_parse = parse_profile_snippet(result.title, result.snippet)
        if candidate_parse is None:
            continue
        if candidate_parse.company_name:
            parsed = candidate_parse
            break
        if parsed is None:
            parsed = candidate_parse

    if parsed is None:
        raise UrlLookupError(
            "No public search listing was found for this LinkedIn profile. "
            "LinkedIn profiles are login-gated and never fetched directly — only "
            "what a search engine has indexed can be used. If you know where they "
            'work, enter "Full Name, Company Name" in Bulk Contact Lookup instead.'
        )

    # No employer means no domain to look an email up against, so the
    # enrichment is skipped entirely rather than searched for in vain.
    domain: str | None = None
    emails: list[dict] = []
    if parsed.company_name:
        domain, emails = await _resolve_domain_and_email(
            provider, settings, company_name=parsed.company_name, full_name=parsed.name
        )

    candidate = DiscoveredCompany(
        company_name=parsed.company_name,
        website=f"https://{domain}" if domain else None,
        source=f"social_snippet:{provider.name}",
        source_url=url,
        is_mock=provider.name == "mock",
        social_profiles=[{"platform": platform, "url": url}],
        contact_person_name=parsed.name,
        contact_person_title=parsed.title,
        emails=emails,
    )
    preview = _build_preview(db, candidate, owner_id)
    logger.info(
        "Profile snippet lookup %s previewed contact=%r at company=%r (not saved)",
        url,
        parsed.name,
        parsed.company_name,
    )
    return preview


async def _preview_from_name_and_company(
    db: Session, *, full_name: str, company_name: str, owner_id: str
) -> dict:
    """Bulk-lookup path for an item given as a plain name + company (no
    profile URL to derive them from) — goes straight to the same
    domain-resolution + email enrichment the profile-snippet fallback uses.
    Returns the contact even when no email was found — the customer is
    charged only for an email that actually turned up."""
    settings = get_settings()
    provider = get_search_provider(settings)
    domain, emails = await _resolve_domain_and_email(
        provider, settings, company_name=company_name, full_name=full_name
    )

    candidate = DiscoveredCompany(
        company_name=company_name,
        website=f"https://{domain}" if domain else None,
        source=f"bulk_lookup:{provider.name}",
        is_mock=provider.name == "mock",
        contact_person_name=full_name,
        emails=emails,
    )
    preview = _build_preview(db, candidate, owner_id)
    logger.info(
        "Bulk lookup previewed contact=%r at company=%r (not saved)", full_name, company_name
    )
    return preview


async def bulk_contact_lookup_preview(db: Session, items: list, owner_id: str) -> list[dict]:
    """Look up several people at once — each item is either a LinkedIn
    profile URL (routed through the exact same logic as a single "paste a
    link" lookup) or a plain name + company pair. Items are resolved one
    at a time rather than concurrently: every path ends up running a
    synchronous SQLAlchemy query against the shared request-scoped `db`
    Session (via `_build_preview`), and a Session isn't safe for
    concurrent/interleaved use even across cooperatively-scheduled
    coroutines. One item failing — for any reason, not just an
    unreachable URL — never affects the others: each is caught and
    reported independently. Preview only, same as everywhere else —
    nothing here writes to the database.
    """

    async def _resolve_one(item) -> dict:
        try:
            if item.url is not None:
                preview = await discover_from_url_preview(db, str(item.url), owner_id)
            else:
                preview = await _preview_from_name_and_company(
                    db,
                    full_name=item.full_name,
                    company_name=item.company_name,
                    owner_id=owner_id,
                )
            return {"item": item, "success": True, "error": None, "preview": preview}
        except UrlLookupError as exc:
            return {"item": item, "success": False, "error": str(exc), "preview": None}
        except Exception:
            logger.exception("Bulk lookup: item failed unexpectedly — skipping. item=%r", item)
            return {
                "item": item,
                "success": False,
                "error": "Something went wrong looking this one up.",
                "preview": None,
            }

    return [await _resolve_one(item) for item in items]


def _preview_payload_to_candidate(payload) -> DiscoveredCompany:
    """Convert a `SaveCompanyRequestSchema` (the client echoing back a
    preview it wants saved) into a `DiscoveredCompany` for persistence."""
    return DiscoveredCompany(
        company_name=payload.company_name,
        website=payload.website,
        country=payload.country,
        city=payload.city,
        region=payload.region,
        industry=payload.industry,
        description=payload.description,
        activities=list(payload.activities),
        products=list(payload.products),
        keywords=list(payload.keywords),
        source=payload.source,
        source_url=payload.source_url,
        is_mock=payload.is_mock,
        contact_page_url=payload.contact_page_url,
        social_profiles=[p.model_dump() for p in payload.social_profiles],
        emails=[e.model_dump() for e in payload.emails],
        phones=[p.model_dump() for p in payload.phones],
        contact_person_name=payload.contact_person_name,
        contact_person_title=payload.contact_person_title,
    )


def save_candidate(db: Session, payload, owner_id: str) -> Company:
    """Persist one previewed (not-yet-saved) candidate — the explicit
    "Save" action. Goes through the exact same dedup/merge logic as
    automated saves, so saving something that already exists just merges
    into it rather than creating a duplicate."""
    candidate = _preview_payload_to_candidate(payload)
    company, _ = _persist_candidate(db, candidate, owner_id=owner_id, context="manual save")
    if company is None:
        raise CompanySaveError("Could not save this company. Please try again.")
    db.commit()
    db.refresh(company)
    return company


def save_candidates_bulk(
    db: Session, payloads: list, owner_id: str
) -> tuple[list[Company | None], int, int]:
    """Persist several previewed candidates at once ("Save All").

    Returns one result per input payload, in the same order — `None`
    where that particular candidate failed to persist. Callers need this
    positional alignment to report per-row outcomes back to the UI;
    matching a saved company back to its input row by mutable fields like
    `company_name` doesn't work reliably, since a confident-match merge
    keeps the *existing* saved company's name, not the incoming
    candidate's.
    """
    new_count = 0
    duplicate_count = 0
    results: list[Company | None] = []
    for payload in payloads:
        candidate = _preview_payload_to_candidate(payload)
        company, is_new = _persist_candidate(
            db, candidate, owner_id=owner_id, context="bulk save"
        )
        results.append(company)
        if company is None:
            continue
        if is_new:
            new_count += 1
        else:
            duplicate_count += 1
    db.commit()
    for company in results:
        if company is not None:
            db.refresh(company)
    return results, new_count, duplicate_count


def _filtered_companies_stmt(
    *,
    owner_id: str,
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = None,
    min_lead_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_exported: bool | None = None,
    search: str | None = None,
):
    """Shared WHERE-clause builder for `list_companies` and `export_companies`.

    Kept in one place (Phase 9: advanced search & filtering) so pagination
    and export always agree on what "matches the filters" means — always
    within one account's own companies.
    """
    stmt = select(Company).where(Company.owner_id == owner_id)
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
    if has_exported is True:
        stmt = stmt.where(Company.exported_at.isnot(None))
    elif has_exported is False:
        stmt = stmt.where(Company.exported_at.is_(None))
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(Company.normalized_name.like(like))
    return stmt


def list_companies(
    db: Session,
    *,
    owner_id: str,
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = None,
    min_lead_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_exported: bool | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Company], int]:
    stmt = _filtered_companies_stmt(
        owner_id=owner_id,
        country=country,
        region=region,
        industry=industry,
        product=product,
        min_relevance=min_relevance,
        min_lead_score=min_lead_score,
        has_email=has_email,
        has_phone=has_phone,
        has_exported=has_exported,
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
    owner_id: str,
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = None,
    min_lead_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_exported: bool | None = None,
    search: str | None = None,
    mark_exported: bool = True,
) -> list[Company]:
    """Return every company matching the filters, unpaginated (Phase 8: export).

    `mark_exported=True` (the default) stamps `exported_at` on each
    returned company — set it `False` for a "preview" call that shouldn't
    count as an export (none currently do, but keeps the option open).
    """
    stmt = _filtered_companies_stmt(
        owner_id=owner_id,
        country=country,
        region=region,
        industry=industry,
        product=product,
        min_relevance=min_relevance,
        min_lead_score=min_lead_score,
        has_email=has_email,
        has_phone=has_phone,
        has_exported=has_exported,
        search=search,
    ).order_by(Company.relevance_score.desc(), Company.discovered_at.desc())
    stmt = stmt.limit(MAX_EXPORT_ROWS)
    companies = list(db.execute(stmt).scalars().all())

    if mark_exported and companies:
        now = utcnow()
        for company in companies:
            company.exported_at = now
        db.commit()

    return companies


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
                "Exported Date": c.exported_at.isoformat() if c.exported_at else "",
            }
        )
    return rows


def get_company(db: Session, company_id: str, owner_id: str) -> Company | None:
    """One of `owner_id`'s companies — another account's company is treated as not found."""
    company = db.get(Company, company_id)
    return company if company is not None and company.owner_id == owner_id else None


def list_searches(
    db: Session, *, owner_id: str, page: int = 1, page_size: int = 25
) -> tuple[list[SearchQuery], int]:
    stmt = select(SearchQuery).where(SearchQuery.owner_id == owner_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = (
        stmt.order_by(SearchQuery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total
