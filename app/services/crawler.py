"""The background crawler: reads petroleum companies' websites on a
schedule, so the contact directory grows between searches instead of only
during them.

Two parts, both run by `run_crawler` (the worker calls it every 30 minutes;
an admin can also start one from the Directory page):

* Seeding — a few search-provider queries per run ("crude oil trading
  Nigeria") find company sites nobody has searched for yet. Each query is
  one search credit, and the least recently run one goes next so the whole
  list is covered in turn. Every site a customer's search turns up joins the
  queue too, for free.
* Crawling — the sites that are due are read exactly as a search reads them
  (homepage, Contact, About/Team/Imprint), and every address found goes into
  the directory. Reading a site costs nothing. A site is read again after
  `CRAWLER_RECRAWL_DAYS`; one that fails is retried later each time.

A site whose robots.txt asks PetroLeadBot not to crawl it is left alone.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import product
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.net_guard import MAX_REDIRECTS, block_internal_requests
from app.database.models import (
    ContactRecord,
    CrawlSeed,
    CrawlTarget,
    EmailDomain,
    utcnow,
)
from app.discovery.extractor import enrich_from_website
from app.discovery.search import SearchQuotaExceededError, get_search_provider
from app.discovery.types import DiscoveredCompany
from app.services import contact_directory

logger = logging.getLogger("petrolead.services.crawler")

# Where the oil and gas trade is, and what its companies call themselves.
# Every pairing is one seed search.
SEED_COUNTRIES = (
    "Nigeria", "Angola", "Ghana", "Egypt", "Libya", "Algeria", "South Africa", "Kenya",
    "United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait", "Oman", "Iraq", "Bahrain",
    "India", "Singapore", "Malaysia", "Indonesia", "China", "South Korea", "Japan", "Turkey",
    "Netherlands", "United Kingdom", "Norway", "Germany", "Spain", "Italy", "Kazakhstan",
    "Azerbaijan", "United States", "Canada", "Mexico", "Brazil", "Colombia", "Argentina",
    "Australia",
)  # fmt: skip
SEED_ACTIVITIES = (
    "crude oil trading company",
    "petroleum products supplier",
    "oil refinery",
    "fuel distributor",
    "LPG supplier",
    "bitumen supplier",
    "lubricants manufacturer",
    "oil and gas services company",
)
SEED_QUERIES = tuple(f"{activity} {country}" for country, activity in product(
    SEED_COUNTRIES, SEED_ACTIVITIES
))  # fmt: skip

# The longest a failing site waits before its next try, in days.
MAX_BACKOFF_DAYS = 30


@dataclass
class CrawlSummary:
    seed_searches: int = 0
    sites_added: int = 0
    sites_crawled: int = 0
    sites_failed: int = 0
    sites_skipped_by_robots: int = 0
    emails_found: int = 0
    notes: list[str] = field(default_factory=list)


def enqueue(
    db: Session,
    *,
    domain: str,
    website: str,
    company_name: str | None,
    source: str,
    crawled: bool,
) -> bool:
    """Queue a company site. `crawled` means it was just read (by a
    search), so its first visit can wait a full cycle. Returns whether it
    was new. The caller commits."""
    if db.get(CrawlTarget, domain) is not None:
        return False
    now = utcnow()
    db.add(
        CrawlTarget(
            domain=domain,
            website=website,
            company_name=company_name,
            source=source,
            last_crawled_at=now if crawled else None,
            next_crawl_at=now + timedelta(days=get_settings().crawler_recrawl_days)
            if crawled
            else now,
        )
    )
    db.flush()
    return True


def enqueue_candidates(db: Session, candidates: list[DiscoveredCompany]) -> None:
    """Queue every real company site among a search's results. They were
    just read by the search, so they're due again in a full cycle. Never
    raises."""
    try:
        for candidate in candidates:
            domain = contact_directory.company_mail_domain(candidate)
            if domain:
                enqueue(
                    db,
                    domain=domain,
                    website=candidate.website or f"https://{domain}",
                    company_name=candidate.company_name,
                    source="search",
                    crawled=True,
                )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Couldn't queue search results for crawling", exc_info=True)


def _sync_seeds(db: Session) -> None:
    """Make sure every seed query has a row; new ones run first."""
    existing = set(db.execute(select(CrawlSeed.query)).scalars())
    for query in SEED_QUERIES:
        if query not in existing:
            db.add(CrawlSeed(query=query))
    db.commit()


async def run_seed_searches(db: Session, settings: Settings, summary: CrawlSummary) -> None:
    count = settings.crawler_seed_searches_per_run
    if count <= 0:
        return
    provider = get_search_provider(settings)
    if provider.name == "mock":
        summary.notes.append("Seeding skipped: no search provider is configured.")
        return

    _sync_seeds(db)
    seeds = list(
        db.execute(
            select(CrawlSeed).order_by(CrawlSeed.last_run_at.asc().nulls_first()).limit(count)
        ).scalars()
    )
    for seed in seeds:
        try:
            results = await provider.search(seed.query, limit=10)
        except SearchQuotaExceededError:
            summary.notes.append("Seeding stopped: the search provider's quota is used up.")
            break
        except Exception:
            logger.warning("Seed search failed: %r", seed.query, exc_info=True)
            continue
        summary.seed_searches += 1
        added = 0
        for result in results:
            domain = contact_directory.site_domain(result.url)
            if domain and enqueue(
                db,
                domain=domain,
                website=f"https://{domain}",
                company_name=None,
                source="seed",
                crawled=False,
            ):
                added += 1
        seed.last_run_at = utcnow()
        seed.sites_found += added
        summary.sites_added += added
        db.commit()


async def _robots_allows(client: httpx.AsyncClient, website: str, user_agent: str) -> bool:
    """Whether robots.txt lets us read the homepage. No robots.txt, or one
    that can't be fetched, means no objection — the usual convention."""
    try:
        response = await client.get(website.rstrip("/") + "/robots.txt")
    except Exception:
        return True
    if response.status_code >= 400:
        return True
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser.can_fetch(user_agent, website)


async def _visit(
    target: CrawlTarget, settings: Settings, semaphore: asyncio.Semaphore
) -> tuple[CrawlTarget, DiscoveredCompany | None, str]:
    """Read one site. Returns the result and "ok", "failed" or "robots"."""
    async with semaphore:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            headers={"User-Agent": settings.http_user_agent},
            event_hooks={"request": [block_internal_requests]},
        ) as client:
            if not await _robots_allows(client, target.website, settings.http_user_agent):
                return target, None, "robots"

        company = DiscoveredCompany(
            # The website as a placeholder name tells the extractor to take
            # the real one from the page title (see WebsiteSource).
            company_name=target.company_name or target.website,
            website=target.website,
            source="crawler",
            source_url=target.website,
        )
        try:
            enriched = await enrich_from_website(company, settings=settings)
        except Exception:
            logger.warning("Crawling %s failed", target.domain, exc_info=True)
            return target, None, "failed"

    learned_anything = bool(
        enriched.company_name != enriched.website
        or enriched.description
        or enriched.contact_page_url
        or enriched.social_profiles
        or enriched.emails
    )
    return target, enriched, "ok" if learned_anything else "failed"


async def crawl_due_sites(db: Session, settings: Settings, summary: CrawlSummary) -> None:
    now = utcnow()
    targets = list(
        db.execute(
            select(CrawlTarget)
            .where(CrawlTarget.next_crawl_at <= now)
            .order_by(CrawlTarget.next_crawl_at)
            .limit(settings.crawler_batch_size)
        ).scalars()
    )
    if not targets:
        return

    # Sites are fetched concurrently; the database is only touched after,
    # one result at a time, since a session can't be shared across tasks.
    semaphore = asyncio.Semaphore(settings.max_concurrent_fetches)
    visits = await asyncio.gather(*(_visit(t, settings, semaphore) for t in targets))

    recrawl = timedelta(days=settings.crawler_recrawl_days)
    for target, enriched, outcome in visits:
        target.last_crawled_at = utcnow()
        if outcome == "robots":
            summary.sites_skipped_by_robots += 1
            target.next_crawl_at = utcnow() + recrawl
            continue
        if outcome == "failed":
            summary.sites_failed += 1
            target.failures += 1
            backoff_days = min(2**target.failures, MAX_BACKOFF_DAYS)
            target.next_crawl_at = utcnow() + timedelta(days=backoff_days)
            continue

        summary.sites_crawled += 1
        target.failures = 0
        target.next_crawl_at = utcnow() + recrawl
        target.emails_found = len(enriched.emails)
        summary.emails_found += len(enriched.emails)
        if enriched.company_name and enriched.company_name != enriched.website:
            target.company_name = enriched.company_name[:500]
        contact_directory.record_candidates(db, [enriched])
    db.commit()


async def run_crawler(db: Session, settings: Settings | None = None) -> CrawlSummary:
    """One crawler run: seed searches, then the sites that are due."""
    settings = settings or get_settings()
    summary = CrawlSummary()
    if not settings.crawler_enabled:
        summary.notes.append("The crawler is turned off (CRAWLER_ENABLED=false).")
        return summary
    await run_seed_searches(db, settings, summary)
    await crawl_due_sites(db, settings, summary)
    logger.info(
        "Crawler run: %d seed searches, %d sites added, %d crawled, %d failed, "
        "%d skipped by robots.txt, %d emails found",
        summary.seed_searches,
        summary.sites_added,
        summary.sites_crawled,
        summary.sites_failed,
        summary.sites_skipped_by_robots,
        summary.emails_found,
    )
    return summary


def directory_stats(db: Session) -> dict:
    """How big the directory and the crawl queue are, for the admin page."""

    def count(stmt) -> int:
        return db.execute(stmt).scalar_one()

    now = utcnow()
    return {
        "contacts": count(select(func.count()).select_from(ContactRecord)),
        "named_contacts": count(
            select(func.count())
            .select_from(ContactRecord)
            .where(ContactRecord.name_key.is_not(None))
        ),
        "confirmed_contacts": count(
            select(func.count()).select_from(ContactRecord).where(ContactRecord.is_valid.is_(True))
        ),
        "company_domains": count(select(func.count(func.distinct(ContactRecord.domain)))),
        "domains_with_known_format": sum(
            1 for counts in db.execute(select(EmailDomain.pattern_counts)).scalars() if counts
        ),
        "sites_queued": count(select(func.count()).select_from(CrawlTarget)),
        "sites_due": count(
            select(func.count()).select_from(CrawlTarget).where(CrawlTarget.next_crawl_at <= now)
        ),
        "sites_crawled_last_24h": count(
            select(func.count())
            .select_from(CrawlTarget)
            .where(CrawlTarget.last_crawled_at >= now - timedelta(days=1))
        ),
        "seed_searches_run": count(
            select(func.count()).select_from(CrawlSeed).where(CrawlSeed.last_run_at.is_not(None))
        ),
        "seed_searches_total": len(SEED_QUERIES),
    }
