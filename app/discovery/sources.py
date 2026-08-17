"""Source connector architecture.

    BaseSource
        |
        ├── SearchSource    (web search engine → companies)   [implemented]
        ├── WebsiteSource   (single known site → one company) [implemented]
        ├── B2BSource       (B2B directories/marketplaces)     [Phase 6]
        └── SocialSource    (LinkedIn/etc via compliant APIs)  [Phase 5]

Every connector returns a `list[DiscoveredCompany]` — the one shape the
rest of the app (dedup, relevance, persistence, API, frontend) needs to
understand. Adding a new source later means adding a new subclass here,
nothing else changes.

B2BSource and SocialSource are intentionally NOT implemented in Phase 1.
They raise `NotImplementedError` with a clear message rather than
pretending to work — see PETROLEAD roadmap phases 5 and 6. In
particular, SocialSource is designed around compliant APIs / permitted
public data only; it must never bypass login walls, CAPTCHAs, or other
access controls on social platforms.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from app.config import Settings, get_settings
from app.discovery.extractor import company_from_search_result, enrich_from_website
from app.discovery.search import QueryBuilder, SearchProvider, get_search_provider
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
        per_query_limit = max(3, (request.limit // max(len(queries), 1)) + 1)

        companies: list[DiscoveredCompany] = []
        for query in queries:
            if len(companies) >= request.limit:
                break
            try:
                results = await self._provider.search(query, limit=per_query_limit)
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


class B2BSource(BaseSource):
    """B2B directory / marketplace connector — planned for Phase 6.

    Will integrate with permitted B2B trade directories (e.g. via their
    official APIs or public listing pages) to surface companies that
    list petroleum products/services. Not implemented in Phase 1.
    """

    name = "b2b_directory"

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveredCompany]:
        raise NotImplementedError(
            "B2BSource is planned for Phase 6 and is not implemented yet. "
            "It will connect to B2B directories via permitted APIs/public listings only."
        )


class SocialSource(BaseSource):
    """Social/company-profile connector — planned for Phase 5.

    Designed to use compliant, official APIs (e.g. LinkedIn's official
    Marketing/Partner APIs) or explicitly permitted public data only.
    Will never bypass login walls, CAPTCHAs, or platform access controls.
    Not implemented in Phase 1.
    """

    name = "social"

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveredCompany]:
        raise NotImplementedError(
            "SocialSource is planned for Phase 5 and is not implemented yet. "
            "It will rely exclusively on compliant APIs / permitted public data."
        )
