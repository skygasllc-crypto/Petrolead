"""Search provider failures are reported cleanly.

HTTP 429 (out of credits / rate-limited) becomes a `SearchQuotaExceededError`
that stops a discovery run and reaches the user as a clear message instead
of an empty result or a misleading "login-gated" error. No provider error
may ever carry the API key — Google CSE, SerpApi and SearchAPI.io send it
as a query parameter, and httpx's own messages embed the full URL.

The providers' HTTP calls run against `httpx.MockTransport`, so nothing
here touches the network.
"""

import json
import traceback

import httpx
import pytest

from app.config import Settings
from app.discovery import search as search_module
from app.discovery import sources as sources_module
from app.discovery.search import (
    GoogleCSEProvider,
    SearchApiIoProvider,
    SearchProviderError,
    SearchQuotaExceededError,
    SearchResultItem,
    SerpApiProvider,
    SerperProvider,
)
from app.discovery.sources import SearchSource
from app.discovery.types import DiscoveryRequest
from app.services import company_service

API_KEY = "test-secret-api-key-0123456789"
_RealAsyncClient = httpx.AsyncClient

_PROVIDER_CASES = [
    (SearchApiIoProvider, {"searchapi_io_api_key": API_KEY}),
    (SerpApiProvider, {"serpapi_api_key": API_KEY}),
    (GoogleCSEProvider, {"google_cse_api_key": API_KEY, "google_cse_engine_id": "engine"}),
    (SerperProvider, {"serper_api_key": API_KEY}),
]


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _use_transport(monkeypatch, handler) -> None:
    def client_factory(*args, **kwargs):
        return _RealAsyncClient(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(search_module.httpx, "AsyncClient", client_factory)


def _formatted(exc: BaseException) -> str:
    """What a `logger.warning(..., exc_info=True)` would write."""
    return "".join(traceback.format_exception(exc))


class TestProviderErrors:
    @pytest.mark.parametrize("provider_cls,overrides", _PROVIDER_CASES)
    async def test_429_raises_quota_error_without_the_key(
        self, monkeypatch, provider_cls, overrides
    ):
        _use_transport(monkeypatch, lambda request: httpx.Response(429, json={"error": "limit"}))

        with pytest.raises(SearchQuotaExceededError) as excinfo:
            await provider_cls(_settings(**overrides)).search("fuel supplier")

        assert "429" in str(excinfo.value)
        assert API_KEY not in _formatted(excinfo.value)

    @pytest.mark.parametrize("provider_cls,overrides", _PROVIDER_CASES)
    async def test_other_http_errors_are_not_quota_errors(
        self, monkeypatch, provider_cls, overrides
    ):
        _use_transport(monkeypatch, lambda request: httpx.Response(500))

        with pytest.raises(SearchProviderError) as excinfo:
            await provider_cls(_settings(**overrides)).search("fuel supplier")

        assert not isinstance(excinfo.value, SearchQuotaExceededError)
        assert "500" in str(excinfo.value)
        assert API_KEY not in _formatted(excinfo.value)

    async def test_network_error_hides_the_key_bearing_url(self, monkeypatch):
        def handler(request):
            raise httpx.ConnectError(f"cannot connect to {request.url}", request=request)

        _use_transport(monkeypatch, handler)

        with pytest.raises(SearchProviderError) as excinfo:
            await SearchApiIoProvider(_settings(searchapi_io_api_key=API_KEY)).search("fuel")

        assert "ConnectError" in str(excinfo.value)
        assert API_KEY not in _formatted(excinfo.value)

    async def test_successful_response_still_parses(self, monkeypatch):
        def handler(request):
            assert request.url.params["api_key"] == API_KEY
            return httpx.Response(
                200,
                json={"organic_results": [{"title": "Falcon Fuel", "link": "https://falcon.example"}]},
            )

        _use_transport(monkeypatch, handler)

        results = await SearchApiIoProvider(_settings(searchapi_io_api_key=API_KEY)).search("fuel")

        assert [(r.title, r.url) for r in results] == [("Falcon Fuel", "https://falcon.example")]

    async def test_serper_posts_query_with_key_in_header(self, monkeypatch):
        def handler(request):
            assert request.method == "POST"
            assert request.headers["X-API-KEY"] == API_KEY
            assert API_KEY not in str(request.url)
            assert json.loads(request.content) == {"q": "diesel supplier"}
            return httpx.Response(
                200,
                json={
                    "organic": [
                        {"title": f"Fuel {i}", "link": f"https://fuel{i}.example", "snippet": "s"}
                        for i in range(10)
                    ]
                },
            )

        _use_transport(monkeypatch, handler)

        results = await SerperProvider(_settings(serper_api_key=API_KEY)).search(
            "diesel supplier", limit=3
        )

        assert [r.url for r in results] == [f"https://fuel{i}.example" for i in range(3)]
        assert results[0].snippet == "s"


class _QuotaAfterProvider:
    """Answers the first `ok_calls` queries (optionally only non-`site:`
    ones), then behaves like a provider that has run out of credits."""

    name = "fake_real_provider"

    def __init__(self, ok_calls: int, *, fail_site_queries: bool = False):
        self.calls = 0
        self._ok_calls = ok_calls
        self._fail_site_queries = fail_site_queries

    async def search(self, query, *, limit=10):
        self.calls += 1
        if self._fail_site_queries and query.startswith("site:"):
            raise SearchQuotaExceededError("quota exceeded (HTTP 429)")
        if self.calls > self._ok_calls:
            raise SearchQuotaExceededError("quota exceeded (HTTP 429)")
        return [
            SearchResultItem(
                title=f"Falcon Fuel Trading {self.calls}", url=f"https://fuel{self.calls}.example"
            )
        ]


def _multi_query_request() -> DiscoveryRequest:
    return DiscoveryRequest(
        country="United Arab Emirates", industry="Oil & Gas", products=["diesel"], limit=100
    )


class TestSearchSourceStopsOnQuota:
    async def test_raises_when_quota_hits_before_any_result(self):
        provider = _QuotaAfterProvider(ok_calls=0)

        with pytest.raises(SearchQuotaExceededError):
            await SearchSource(provider, enrich=False).discover(_multi_query_request())

        assert provider.calls == 1

    async def test_keeps_partial_results_and_stops_querying(self):
        provider = _QuotaAfterProvider(ok_calls=1)

        companies = await SearchSource(provider, enrich=False).discover(_multi_query_request())

        assert len(companies) == 1
        assert provider.calls == 2


async def _no_enrichment(company, *, settings):
    return company


class TestQuotaReachesTheUser:
    def test_discover_fails_with_quota_message(self, client, monkeypatch):
        monkeypatch.setattr(
            sources_module, "get_search_provider", lambda settings: _QuotaAfterProvider(ok_calls=0)
        )

        response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )

        assert response.status_code == 502
        assert "quota" in response.json()["detail"]

    def test_discover_keeps_results_when_only_one_source_hits_quota(self, client, monkeypatch):
        monkeypatch.setattr(
            sources_module,
            "get_search_provider",
            lambda settings: _QuotaAfterProvider(ok_calls=100, fail_site_queries=True),
        )
        monkeypatch.setattr(sources_module, "enrich_from_website", _no_enrichment)

        response = client.post(
            "/api/discover",
            json={"country": "United Arab Emirates", "limit": 10, "include_social_search": True},
        )

        assert response.status_code == 200
        assert response.json()["result_count"] > 0

    def test_profile_lookup_reports_quota_not_login_gate(self, client, monkeypatch):
        monkeypatch.setattr(
            company_service, "get_search_provider", lambda settings: _QuotaAfterProvider(ok_calls=0)
        )

        response = client.post(
            "/api/discover-url", json={"url": "https://www.linkedin.com/in/jane-doe"}
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "quota" in detail
        assert "login-gated" not in detail
