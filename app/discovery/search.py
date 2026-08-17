"""Query generation and pluggable web-search providers.

`QueryBuilder` turns a `DiscoveryRequest` into a set of intelligent,
reusable search queries (not a hard-coded list). `SearchProvider` is
the abstraction that lets us swap Google Programmable Search / Bing /
SerpApi / a mock provider purely through configuration
(`SEARCH_PROVIDER` in `.env`) — nothing downstream needs to know which
one is active.
"""

from __future__ import annotations

import itertools
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from app.discovery.types import DiscoveryRequest

logger = logging.getLogger("petrolead.discovery.search")

# --- Query generation --------------------------------------------------------

_INDUSTRY_PHRASES = {
    "Petroleum Trading": ["petroleum trading company", "petroleum trading"],
    "Oil & Gas": ["oil and gas company", "oil & gas"],
    "Fuel Supply": ["fuel supplier", "fuel supply company"],
    "Refinery": ["oil refinery", "petroleum refinery"],
    "Tank Storage": ["tank storage terminal", "petroleum tank storage"],
    "Petroleum Logistics": ["petroleum logistics company", "fuel logistics"],
    "Bunkering": ["bunkering company", "marine fuel bunkering"],
    "Energy Trading": ["energy trading company"],
    "Oil Terminal": ["oil terminal operator"],
    "Distributor": ["petroleum products distributor", "fuel distributor"],
}

_GENERIC_PETROLEUM_PHRASES = ["petroleum company", "oil trading company", "fuel trading company"]


class QueryBuilder:
    """Builds a de-duplicated list of search-engine queries for a discovery request."""

    def build(self, request: DiscoveryRequest) -> list[str]:
        location_terms = self._location_terms(request)
        subject_phrases = self._subject_phrases(request)

        queries: list[str] = []
        for phrase, location in itertools.product(subject_phrases, location_terms or [""]):
            queries.append(self._compose(phrase, location))

        # Keyword-driven queries, one per keyword, combined with location.
        for keyword in request.keywords:
            for location in location_terms or [""]:
                queries.append(self._compose(keyword, location))

        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique_queries: list[str] = []
        for q in queries:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                unique_queries.append(q)
        return unique_queries

    @staticmethod
    def _location_terms(request: DiscoveryRequest) -> list[str]:
        terms = [t for t in (request.city, request.country, request.region) if t]
        return terms

    @staticmethod
    def _subject_phrases(request: DiscoveryRequest) -> list[str]:
        phrases: list[str] = []

        for product in request.products:
            phrases.append(f"{product} trader")
            phrases.append(f"{product} supplier")

        if request.activity:
            phrases.append(request.activity)

        if request.industry:
            phrases.extend(_INDUSTRY_PHRASES.get(request.industry, [request.industry.lower()]))

        if not phrases:
            phrases.extend(_GENERIC_PETROLEUM_PHRASES)

        return phrases

    @staticmethod
    def _compose(subject: str, location: str) -> str:
        subject = subject.strip()
        location = location.strip()
        if subject and location:
            return f'"{subject}" "{location}"'
        return f'"{subject}"' if subject else f'"{location}"'


# --- Search provider abstraction ---------------------------------------------


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str = ""


class SearchProvider(ABC):
    """Base interface every web-search backend implements."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        """Run a single query and return raw search results."""
        raise NotImplementedError


class GoogleCSEProvider(SearchProvider):
    """Google Programmable Search Engine (Custom Search JSON API).

    Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ENGINE_ID.
    https://programmablesearchengine.google.com/
    """

    name = "google_cse"
    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, settings: Settings):
        self._api_key = settings.google_cse_api_key
        self._engine_id = settings.google_cse_engine_id
        self._timeout = settings.http_timeout_seconds

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        if not self._api_key or not self._engine_id:
            raise RuntimeError("Google CSE is not configured (missing API key / engine id).")

        params = {
            "key": self._api_key,
            "cx": self._engine_id,
            "q": query,
            "num": min(limit, 10),
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self.ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()

        items = data.get("items", [])
        return [
            SearchResultItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items
        ]


class BingSearchProvider(SearchProvider):
    """Bing Web Search API (Azure Cognitive Services). Requires BING_SEARCH_API_KEY."""

    name = "bing"
    ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, settings: Settings):
        self._api_key = settings.bing_search_api_key
        self._timeout = settings.http_timeout_seconds

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        if not self._api_key:
            raise RuntimeError("Bing Search is not configured (missing API key).")

        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        params = {"q": query, "count": limit}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self.ENDPOINT, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        items = data.get("webPages", {}).get("value", [])
        return [
            SearchResultItem(
                title=item.get("name", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items
        ]


class SerpApiProvider(SearchProvider):
    """SerpApi (https://serpapi.com/) — hosted search-engine results API."""

    name = "serpapi"
    ENDPOINT = "https://serpapi.com/search"

    def __init__(self, settings: Settings):
        self._api_key = settings.serpapi_api_key
        self._timeout = settings.http_timeout_seconds

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        if not self._api_key:
            raise RuntimeError("SerpApi is not configured (missing API key).")

        params = {"q": query, "api_key": self._api_key, "num": limit}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self.ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()

        items = data.get("organic_results", [])
        return [
            SearchResultItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items
        ]


class MockSearchProvider(SearchProvider):
    """No-API-key-required provider used for local development and UI testing.

    Returns clearly-labeled synthetic results derived from the query itself
    (`is_mock=True` is threaded through to the resulting companies). This is
    NOT real discovered data and must never be presented to a user as such.
    """

    name = "mock"

    # Deterministic word bank so mock companies read as distinct businesses
    # rather than "X Co. 1 / X Co. 2 / X Co. 3" (which is near-identical text
    # and would otherwise trip the fuzzy-name deduplicator).
    _NAME_TEMPLATES = [
        "{subject} {loc} Holdings",
        "Al Manara {subject} Trading",
        "{loc} Horizon Petroleum",
        "Falcon {subject} Trading",
        "{loc} Gulf Energy Partners",
    ]

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        logger.info("MockSearchProvider: generating synthetic results for query=%r", query)
        parts = [p for p in query.split('"') if p.strip()]
        subject = (parts[0].strip() if parts else "").title() or "Petroleum"
        location = (parts[1].strip() if len(parts) > 1 else "").split()[0].title() if len(
            parts
        ) > 1 else ""

        results = []
        for i, template in enumerate(self._NAME_TEMPLATES[: max(1, min(limit, 5))], start=1):
            name = template.format(subject=subject, loc=location or "Global").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            results.append(
                SearchResultItem(
                    title=f"[MOCK] {name}",
                    url=f"https://example-mock-{slug}.test",
                    snippet=(
                        f"[MOCK DATA] Synthetic result #{i} generated for query '{query}'. "
                        "This is not a real discovered company — configure a real "
                        "SEARCH_PROVIDER (Google CSE, Bing, or SerpApi) to discover actual "
                        "companies."
                    ),
                )
            )
        return results


_PROVIDERS: dict[str, type[SearchProvider]] = {
    "google_cse": GoogleCSEProvider,
    "bing": BingSearchProvider,
    "serpapi": SerpApiProvider,
    "mock": MockSearchProvider,
}


def get_search_provider(settings: Settings | None = None) -> SearchProvider:
    settings = settings or get_settings()
    provider_cls = _PROVIDERS.get(settings.search_provider, MockSearchProvider)
    if provider_cls is MockSearchProvider:
        return MockSearchProvider()
    return provider_cls(settings)
