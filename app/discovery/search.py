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

# Each industry carries at least one phrasing that does NOT say "company",
# because many suppliers are sole traders or small outfits whose pages never
# use that word. Seven of these used to be company- or facility-led only,
# which silently excluded exactly the people a supplier search is for.
_INDUSTRY_PHRASES = {
    "Petroleum Trading": ["petroleum trading company", "petroleum trading", "petroleum trader"],
    "Oil & Gas": ["oil and gas company", "oil & gas", "oil and gas supplier"],
    "Fuel Supply": ["fuel supplier", "fuel supply company", "fuel trader"],
    "Refinery": ["oil refinery", "petroleum refinery", "refined products supplier"],
    "Tank Storage": ["tank storage terminal", "petroleum tank storage", "fuel storage provider"],
    "Petroleum Logistics": [
        "petroleum logistics company",
        "fuel logistics",
        "fuel transport supplier",
    ],
    "Bunkering": ["bunkering company", "marine fuel bunkering", "bunker supplier", "bunker trader"],
    "Energy Trading": ["energy trading company", "energy trader", "fuel trading"],
    "Oil Terminal": ["oil terminal operator", "fuel terminal supplier"],
    "Distributor": ["petroleum products distributor", "fuel distributor", "fuel dealer"],
}

# What kind of counterparty to look for. Chosen in the Discover form and
# combined with whatever industry/product was picked, so "suppliers of
# diesel" is expressible directly instead of being inferred from Products.
# "Any" (the default) adds no role wording and leaves the query as it was.
ROLE_PHRASE_SUFFIXES = {
    "Suppliers": ["supplier", "supply company"],
    "Traders": ["trader", "trading company"],
    "Distributors": ["distributor", "dealer"],
    "Producers": ["producer", "refinery"],
    "Buyers": ["buyer", "importer"],
}

# Deliberately not all "... company". Many suppliers are sole traders or
# small outfits whose pages never use that word, so every phrase containing
# it quietly excludes them — which is exactly what "only companies come
# back" looked like.
_GENERIC_PETROLEUM_PHRASES = [
    "petroleum supplier",
    "fuel supplier",
    "oil trader",
    "diesel supplier",
    "petroleum products distributor",
    "petroleum company",
    "oil trading company",
]

# Each query is one search-provider request and therefore one credit, and
# phrases multiply by locations. A bound keeps a single discovery run's
# cost predictable rather than a product of how many filters were filled in.
MAX_QUERIES_PER_REQUEST = 12

# Phase 6 (partial): well-known public B2B trade directories. `site:domain`
# is a standard search-engine operator — it asks the search provider to
# filter its own already-public index to that domain. It never visits the
# directory's servers itself; that only happens if/when a human clicks a
# result. This is why it's safe without per-directory ToS review, and also
# why `SearchSource` (see sources.py) never treats a directory's listing
# URL as the company's own website — no page from these domains is ever
# fetched by this app.
B2B_DIRECTORY_DOMAINS = [
    "tradekey.com",
    "ec21.com",
    "go4worldbusiness.com",
    "tradeindia.com",
    "exportersindia.com",
    "globalsources.com",
    "thomasnet.com",
]

# Phase 5 (partial): social platforms to discover candidates on. Same
# `site:` operator approach and same never-fetch guarantee as
# B2B_DIRECTORY_DOMAINS above. Instagram is here because small suppliers
# often have no website at all and list their email in their bio, which
# search engines show in the snippet.
SOCIAL_DISCOVERY_DOMAINS = ["linkedin.com/company", "facebook.com", "instagram.com"]

# Appended to every social query. The snippet is the only thing read from a
# social page, so a hit whose snippet has no email yields no email; this
# asks the provider for pages whose indexed text mentions one. Google, Bing
# and the SerpApi-style providers all read `OR` between quoted terms.
SOCIAL_EMAIL_HINT = '"email" OR "@gmail.com"'


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

        return self._dedupe(queries)[:MAX_QUERIES_PER_REQUEST]

    def build_b2b_directory_queries(self, request: DiscoveryRequest) -> list[str]:
        """Queries scoped to known B2B directories via `site:` operators.

        Only built when `request.include_b2b_directories` is set — see
        `DiscoveryRequest` for why this is opt-in rather than automatic.
        """
        if not request.include_b2b_directories:
            return []
        return self._site_scoped_queries(request, B2B_DIRECTORY_DOMAINS)

    def build_social_queries(self, request: DiscoveryRequest) -> list[str]:
        """Queries scoped to known social-platform company pages via `site:` operators.

        Only built when `request.include_social_search` is set — see
        `DiscoveryRequest` for why this is opt-in rather than automatic.
        """
        if not request.include_social_search:
            return []
        return [
            f"{q} {SOCIAL_EMAIL_HINT}"
            for q in self._site_scoped_queries(request, SOCIAL_DISCOVERY_DOMAINS)
        ]

    def _site_scoped_queries(self, request: DiscoveryRequest, domains: list[str]) -> list[str]:
        location_terms = self._location_terms(request)
        subject_phrases = self._subject_phrases(request)[:2]  # keep the query count bounded

        queries: list[str] = []
        for domain in domains:
            for phrase, location in itertools.product(subject_phrases, location_terms or [""]):
                base = self._compose(phrase, location)
                queries.append(f"site:{domain} {base}")
        return self._dedupe(queries)

    @staticmethod
    def _dedupe(queries: list[str]) -> list[str]:
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
    def _role_phrases(request: DiscoveryRequest) -> list[str]:
        """Role wording combined with whatever subject was chosen.

        Combined, never substituted: "Bunkering" + "Suppliers" must ask for
        bunker suppliers, not lose the industry. These go first so that the
        query cap can't truncate away the very thing the role was set to
        find.
        """
        suffixes = ROLE_PHRASE_SUFFIXES.get(request.role or "", [])
        if not suffixes:
            return []

        subjects = [p for p in request.products if p]
        if request.industry:
            subjects.append(request.industry)

        if not subjects:
            # No subject to qualify: ask for the role in this trade at large.
            return [f"petroleum {suffix}" for suffix in suffixes]

        return [f"{subject.lower()} {suffix}" for subject in subjects for suffix in suffixes]

    @staticmethod
    def _subject_phrases(request: DiscoveryRequest) -> list[str]:
        phrases: list[str] = QueryBuilder._role_phrases(request)

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
    def _quote_location(location: str) -> str:
        """Quote a multi-word place so "United Arab Emirates" isn't read as
        three loose words. A single word needs no quoting."""
        location = location.strip()
        return f'"{location}"' if " " in location else location

    @staticmethod
    def _compose(subject: str, location: str) -> str:
        """The subject is deliberately NOT quoted.

        A quoted phrase is a hard constraint on Google: `"petroleum company"`
        cannot match a page describing itself as a petroleum *trading*
        company. That cost most of the near-matches, and worst of all on a
        location-less search, where the single quoted phrase was the whole
        query. The location stays quoted because a place name means the
        literal place.
        """
        subject = subject.strip()
        location = location.strip()
        if subject and location:
            return f"{subject} {QueryBuilder._quote_location(location)}"
        return subject or QueryBuilder._quote_location(location)


# --- Search provider abstraction ---------------------------------------------


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str = ""


class SearchProviderError(RuntimeError):
    """A search provider request failed.

    The message deliberately never includes the request URL: Google CSE,
    SerpApi and SearchAPI.io all carry the API key as a query parameter,
    and httpx's own error messages embed the full URL — which is how keys
    used to end up in the server logs.
    """


class SearchQuotaExceededError(SearchProviderError):
    """The provider answered HTTP 429 — out of credits or rate-limited.
    Retrying further queries in the same run is pointless (each one fails
    the same way), so sources stop at the first one."""


def _quota_exceeded_message(provider_name: str) -> str:
    return (
        f"The search provider ({provider_name}) refused the request: quota or rate limit "
        "exceeded (HTTP 429). Check your plan's remaining credits, or switch "
        "SEARCH_PROVIDER in .env to another configured provider."
    )


async def _fetch_json(
    provider_name: str,
    url: str,
    *,
    timeout: float,
    method: str = "GET",
    params: dict | None = None,
    json: dict | None = None,
    headers: dict | None = None,
) -> dict:
    """Call a provider endpoint and return its JSON body, translating every
    failure into a `SearchProviderError` that is safe to log. `from None`
    drops the original httpx exception from the traceback, since its
    message contains the key-bearing URL."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, url, params=params, json=json, headers=headers
            )
    except httpx.HTTPError as exc:
        raise SearchProviderError(
            f"{provider_name}: request failed ({type(exc).__name__})"
        ) from None

    if response.status_code == 429:
        raise SearchQuotaExceededError(_quota_exceeded_message(provider_name))
    if response.is_error:
        raise SearchProviderError(f"{provider_name}: HTTP {response.status_code}")
    return response.json()


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
        data = await _fetch_json(self.name, self.ENDPOINT, params=params, timeout=self._timeout)
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
        data = await _fetch_json(
            self.name, self.ENDPOINT, params=params, timeout=self._timeout, headers=headers
        )
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
        data = await _fetch_json(self.name, self.ENDPOINT, params=params, timeout=self._timeout)
        items = data.get("organic_results", [])
        return [
            SearchResultItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items
        ]


class SearchApiIoProvider(SearchProvider):
    """SearchAPI.io (https://www.searchapi.io/) — hosted Google SERP API.

    Requires SEARCHAPI_IO_API_KEY. Free tier: 100 requests, no credit card
    required at signup — unlike Google CSE (needs a billing account linked)
    or Bing (needs an Azure account with a card on file).
    """

    name = "searchapi_io"
    ENDPOINT = "https://www.searchapi.io/api/v1/search"

    def __init__(self, settings: Settings):
        self._api_key = settings.searchapi_io_api_key
        self._timeout = settings.http_timeout_seconds

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        if not self._api_key:
            raise RuntimeError("SearchAPI.io is not configured (missing API key).")

        params = {"engine": "google", "q": query, "api_key": self._api_key}
        data = await _fetch_json(self.name, self.ENDPOINT, params=params, timeout=self._timeout)

        # `num` is no longer honored by the underlying Google SERP (fixed at
        # 10 results per page as of Sept 2025) — trim to `limit` client-side.
        items = data.get("organic_results", [])
        return [
            SearchResultItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items[:limit]
        ]


class SerperProvider(SearchProvider):
    """Serper.dev (https://serper.dev/) — hosted Google SERP API.

    Requires SERPER_API_KEY. 2,500 free queries with no credit card, then
    prepaid credit packs. The key travels in a header, never the URL.
    `num` isn't sent: Google returns 10 results per page regardless, and
    Serper bills a request asking for more than 10 as two credits.
    """

    name = "serper"
    ENDPOINT = "https://google.serper.dev/search"

    # One credit buys up to 10 results; asking for 11-100 in a single
    # request costs two. So extra results are fetched as extra *pages* of
    # 10 (one credit each) rather than by raising `num`, which is the same
    # results for twice the money. Google itself returns 10 per page.
    RESULTS_PER_PAGE = 10
    # A ceiling on pages per query: without it, one discovery run's cost
    # would scale with whatever limit a caller asked for.
    MAX_PAGES = 3

    def __init__(self, settings: Settings):
        self._api_key = settings.serper_api_key
        self._timeout = settings.http_timeout_seconds

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResultItem]:
        if not self._api_key:
            raise RuntimeError("Serper is not configured (missing API key).")

        pages_needed = min(
            self.MAX_PAGES,
            max(1, -(-limit // self.RESULTS_PER_PAGE)),  # ceil division
        )
        items: list[dict] = []
        for page in range(1, pages_needed + 1):
            # `page` is 1-based; page 1 is sent explicitly so the request is
            # the same shape throughout.
            data = await _fetch_json(
                self.name,
                self.ENDPOINT,
                method="POST",
                json={"q": query, "page": page},
                headers={"X-API-KEY": self._api_key},
                timeout=self._timeout,
            )
            organic = data.get("organic", [])
            items.extend(organic)
            # A short page means the results ran out — paying for the next
            # one would buy nothing.
            if len(organic) < self.RESULTS_PER_PAGE or len(items) >= limit:
                break

        return [
            SearchResultItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
            for item in items[:limit]
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

        # The personal-LinkedIn-profile snippet fallback (see
        # `discovery/profile_lookup.py`) queries `site:linkedin.com/in/<slug>`
        # — synthesize a plausible name/headline snippet for it instead of
        # falling through to the generic company-name templates below.
        profile_match = re.search(r"linkedin\.com/in/([a-zA-Z0-9\-_.]+)", query)
        if profile_match:
            slug = profile_match.group(1)
            person_name = " ".join(
                w.capitalize() for w in re.split(r"[-_.]+", slug) if w
            ) or "Petroleum Professional"
            company_name = "Falcon Petroleum Trading"
            title = f"[MOCK] {person_name} - Senior Trading Manager at {company_name} | LinkedIn"
            return [
                SearchResultItem(
                    title=title,
                    url=f"https://linkedin.com/in/{slug}",
                    snippet=(
                        f"[MOCK DATA] Synthetic LinkedIn profile snippet for query {query!r}. "
                        "This is not a real person — configure a real SEARCH_PROVIDER to look "
                        "up actual public profile snippets."
                    ),
                )
            ]

        # B2B/social queries are prefixed with a `site:domain` operator
        # (unquoted) — strip it so subject/location parsing below still
        # finds the actual quoted phrase/location, not the operator itself.
        site_scope = re.match(r"^site:(\S+)\s*", query)
        unscoped_query = re.sub(r"^site:\S+\s*", "", query).replace(SOCIAL_EMAIL_HINT, "")
        parts = [p for p in unscoped_query.split('"') if p.strip()]
        subject = (parts[0].strip() if parts else "").title() or "Petroleum"
        location = (parts[1].strip() if len(parts) > 1 else "").split()[0].title() if len(
            parts
        ) > 1 else ""

        results = []
        for i, template in enumerate(self._NAME_TEMPLATES[: max(1, min(limit, 5))], start=1):
            name = template.format(subject=subject, loc=location or "Global").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            # For B2B/social `site:`-scoped queries, host the mock result
            # under the queried domain itself — SocialSource in particular
            # only accepts results whose hostname actually matches a known
            # social domain, same as it would against a real provider.
            url = f"https://{site_scope.group(1)}/mock-{slug}" if site_scope else (
                f"https://example-mock-{slug}.test"
            )
            results.append(
                SearchResultItem(
                    title=f"[MOCK] {name}",
                    url=url,
                    snippet=(
                        f"[MOCK DATA] Synthetic result #{i} generated for query '{query}'. "
                        "This is not a real discovered company — configure a real "
                        "SEARCH_PROVIDER (Google CSE, Bing, or SerpApi) to discover actual "
                        "companies."
                        # A social hit's snippet is where its email comes
                        # from — give it one, as a real snippet would have.
                        + (f" Email: info@{slug}.test" if site_scope else "")
                    ),
                )
            )
        return results


_PROVIDERS: dict[str, type[SearchProvider]] = {
    "google_cse": GoogleCSEProvider,
    "bing": BingSearchProvider,
    "serpapi": SerpApiProvider,
    "searchapi_io": SearchApiIoProvider,
    "serper": SerperProvider,
    "mock": MockSearchProvider,
}


def get_search_provider(settings: Settings | None = None) -> SearchProvider:
    settings = settings or get_settings()
    provider_cls = _PROVIDERS.get(settings.search_provider, MockSearchProvider)
    if provider_cls is MockSearchProvider:
        return MockSearchProvider()
    return provider_cls(settings)
