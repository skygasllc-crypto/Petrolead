"""Source connector architecture.

    BaseSource
        |
        ├── SearchSource    (web search engine → companies)                  [implemented]
        ├── WebsiteSource   (single known site → one company)                [implemented]
        ├── B2BSource       (B2B directories, via search `site:` queries)    [Phase 6, partial]
        └── SocialSource    (social company pages, via search `site:`)       [Phase 5, partial]

Every connector returns a `list[DiscoveredCompany]` — the one shape the
rest of the app (dedup, relevance, persistence, API, frontend) needs to
understand. Adding a new source later means adding a new subclass here,
nothing else changes.

B2BSource and SocialSource are "partial": they discover candidates by
running `site:domain` queries through the already-configured
`SearchProvider` — a standard search-engine operator that only filters
that provider's own already-public index, never contacts the directory
or platform itself. What they do NOT do is fetch/parse an individual
directory listing or social profile page (which would require reviewing
that specific site's terms of service first, or in the case of social
platforms, an approved API partnership) — every candidate they produce
keeps `website=None` specifically so nothing downstream ever fetches
that URL. See PETROLEAD roadmap phases 5 and 6 for what a full
implementation of each would still need.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from app.config import Settings, get_settings
from app.discovery.contacts import SOCIAL_DOMAINS
from app.discovery.extractor import company_from_search_result, enrich_from_website
from app.discovery.search import (
    QueryBuilder,
    SearchProvider,
    SearchQuotaExceededError,
    get_search_provider,
)
from app.discovery.types import DiscoveredCompany, DiscoveryRequest

logger = logging.getLogger("petrolead.discovery.sources")


class BaseSource(ABC):
    """Common interface for every discovery source connector."""

    name: str = "base"

    @abstractmethod
    async def discover(self, request: DiscoveryRequest) -> list[DiscoveredCompany]:
        raise NotImplementedError


class SearchSource(BaseSource):
    """Discovers companies via a configured web-search provider.

    Builds intelligent queries from the request (`QueryBuilder`), runs
    them against the active `SearchProvider`, and turns each result into
    a `DiscoveredCompany`. Optionally enriches results by fetching each
    company's own public homepage.
    """

    name = "web_search"

    def __init__(
        self,
        provider: SearchProvider | None = None,
        *,
        settings: Settings | None = None,
        enrich: bool = True,
    ):
        self._settings = settings or get_settings()
        self._provider = provider or get_search_provider(self._settings)
        self._query_builder = QueryBuilder()
        self._enrich = enrich

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveredCompany]:
        queries = self._query_builder.build(request)
        is_mock = self._provider.name == "mock"
        # A provider bills the same for ten results as for three, so asking
        # for fewer throws away results already paid for — never go below a
        # full page. The cap stops a large `limit` spread over few queries
        # from quietly buying several pages (another credit each) per query.
        results_per_page = 10
        max_per_query = 30
        per_query_limit = min(
            max_per_query,
            max(results_per_page, -(-request.limit // max(len(queries), 1))),
        )

        companies: list[DiscoveredCompany] = []
        for query in queries:
            if len(companies) >= request.limit:
                break
            try:
                results = await self._provider.search(query, limit=per_query_limit)
            except SearchQuotaExceededError as exc:
                # Every remaining query would fail the same way. Nothing found
                # yet means the whole run failed, so let the caller say why.
                if not companies:
                    raise
                logger.warning(
                    "SearchSource: %s Stopping with %d result(s) so far.", exc, len(companies)
                )
                break
            except Exception as exc:
                logger.warning(
                    "SearchSource: provider=%s failed for query=%r (%s)",
                    self._provider.name,
                    query,
                    exc,
                )
                continue

            logger.info(
                "SearchSource: provider=%s query=%r returned %d result(s)",
                self._provider.name,
                query,
                len(results),
            )
            for result in results:
                if not result.url:
                    continue
                companies.append(
                    company_from_search_result(
                        result,
                        request,
                        source=f"search:{self._provider.name}",
                        is_mock=is_mock,
                    )
                )

        companies = companies[: request.limit]

        if self._enrich and not is_mock:
            companies = await self._enrich_all(companies)

        return companies

    async def _enrich_all(self, companies: list[DiscoveredCompany]) -> list[DiscoveredCompany]:
        semaphore = asyncio.Semaphore(self._settings.max_concurrent_fetches)

        async def _bounded(company: DiscoveredCompany) -> DiscoveredCompany:
            async with semaphore:
                return await enrich_from_website(company, settings=self._settings)

        return await asyncio.gather(*(_bounded(c) for c in companies))


class WebsiteSource(BaseSource):
    """Discovers a single company by directly fetching a known website URL."""

    name = "website"

    def __init__(self, url: str, *, settings: Settings | None = None):
        self._url = url
        self._settings = settings or get_settings()

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveredCompany]:
        placeholder = DiscoveredCompany(
            company_name=self._url,
            website=self._url,
            country=request.country,
            city=request.city,
            region=request.region,
            industry=request.industry,
            source=self.name,
            source_url=self._url,
        )
        enriched = await enrich_from_website(placeholder, settings=self._settings)
        return [enriched]


class _SiteScopedSearchSource(BaseSource):
    """Shared plumbing for B2BSource/SocialSource: run `site:`-scoped queries
    through the configured `SearchProvider` and turn hits into candidates
    with `website=None` (see module docstring for why)."""

    def __init__(self, provider: SearchProvider | None = None, *, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._provider = provider or get_search_provider(self._settings)
        self._query_builder = QueryBuilder()

    def _build_queries(self, request: DiscoveryRequest) -> list[str]:
        raise NotImplementedError

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveredCompany]:
        queries = self._build_queries(request)
        if not queries:
            return []

        is_mock = self._provider.name == "mock"
        per_query_limit = max(2, (request.limit // max(len(queries), 1)) + 1)

        companies: list[DiscoveredCompany] = []
        for query in queries:
            if len(companies) >= request.limit:
                break
            try:
                results = await self._provider.search(query, limit=per_query_limit)
            except SearchQuotaExceededError as exc:
                if not companies:
                    raise
                logger.warning(
                    "%s: %s Stopping with %d result(s) so far.",
                    type(self).__name__,
                    exc,
                    len(companies),
                )
                break
            except Exception as exc:
                logger.warning(
                    "%s: provider=%s failed for query=%r (%s)",
                    type(self).__name__,
                    self._provider.name,
                    query,
                    exc,
                )
                continue

            logger.info(
                "%s: provider=%s query=%r returned %d result(s)",
                type(self).__name__,
                self._provider.name,
                query,
                len(results),
            )
            for result in results:
                candidate = self._candidate_from_result(result, request, is_mock=is_mock)
                if candidate is not None:
                    companies.append(candidate)

        return companies[: request.limit]

    def _candidate_from_result(self, result, request, *, is_mock):
        if not result.url:
            return None
        return company_from_search_result(
            result,
            request,
            source=f"{self.name}:{self._provider.name}",
            is_mock=is_mock,
            treat_url_as_website=False,
        )


class B2BSource(_SiteScopedSearchSource):
    """B2B trade-directory discovery via search-engine `site:` queries (Phase 6, partial).

    Implemented: finding listings on well-known directories
    (`discovery.search.B2B_DIRECTORY_DOMAINS`) through the configured
    `SearchProvider`. Not implemented: fetching/parsing an individual
    listing page for structured data — that needs each directory's terms
    of service reviewed first.
    """

    name = "b2b_directory"

    def _build_queries(self, request: DiscoveryRequest) -> list[str]:
        return self._query_builder.build_b2b_directory_queries(request)


class SocialSource(_SiteScopedSearchSource):
    """Social-platform company discovery via search-engine `site:` queries (Phase 5, partial).

    Implemented: finding LinkedIn/Facebook company pages
    (`discovery.search.SOCIAL_DISCOVERY_DOMAINS`) through the configured
    `SearchProvider`, recording the matched page as a `SocialProfile` on
    the resulting company. Not implemented: anything needing an approved
    platform API partnership (richer company data, verified pages, etc.).
    This never logs into or scrapes LinkedIn/Facebook — it only reads
    search-engine result snippets, the same trust model as any other web
    search PetroLead runs.
    """

    name = "social"

    def _build_queries(self, request: DiscoveryRequest) -> list[str]:
        return self._query_builder.build_social_queries(request)

    def _candidate_from_result(self, result, request, *, is_mock):
        if not result.url:
            return None
        platform = _match_social_platform(result.url)
        if platform is None:
            # The provider's `site:` scoping is a best-effort filter, not a
            # guarantee — skip anything that doesn't actually match a known
            # social domain rather than guessing.
            return None
        candidate = company_from_search_result(
            result,
            request,
            source=f"{self.name}:{self._provider.name}",
            is_mock=is_mock,
            treat_url_as_website=False,
        )
        candidate.social_profiles = [{"platform": platform, "url": result.url}]
        return candidate


def _match_social_platform(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, platform in SOCIAL_DOMAINS.items():
        if host == domain or host.endswith(f".{domain}"):
            return platform
    return None
