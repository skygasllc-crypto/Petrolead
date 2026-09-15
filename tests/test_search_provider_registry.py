"""`get_search_provider` resolves `SEARCH_PROVIDER` to the right class.

Only registry wiring is covered here — the concrete providers themselves
(GoogleCSEProvider, BingSearchProvider, SerpApiProvider, SearchApiIoProvider)
make live HTTP calls and need real API keys, so they're exercised manually
against the real services rather than in the test suite (same as the
providers this one joins).
"""

from app.config import Settings
from app.discovery.search import (
    BingSearchProvider,
    GoogleCSEProvider,
    MockSearchProvider,
    SearchApiIoProvider,
    SerpApiProvider,
    SerperProvider,
    get_search_provider,
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


class TestGetSearchProvider:
    def test_defaults_to_mock(self):
        provider = get_search_provider(_settings(search_provider="mock"))
        assert isinstance(provider, MockSearchProvider)

    def test_unknown_provider_falls_back_to_mock(self):
        provider = get_search_provider(_settings(search_provider="not-a-real-provider"))
        assert isinstance(provider, MockSearchProvider)

    def test_resolves_google_cse(self):
        provider = get_search_provider(_settings(search_provider="google_cse"))
        assert isinstance(provider, GoogleCSEProvider)

    def test_resolves_bing(self):
        provider = get_search_provider(_settings(search_provider="bing"))
        assert isinstance(provider, BingSearchProvider)

    def test_resolves_serpapi(self):
        provider = get_search_provider(_settings(search_provider="serpapi"))
        assert isinstance(provider, SerpApiProvider)

    def test_resolves_searchapi_io(self):
        provider = get_search_provider(_settings(search_provider="searchapi_io"))
        assert isinstance(provider, SearchApiIoProvider)
        assert provider.name == "searchapi_io"

    def test_resolves_serper(self):
        provider = get_search_provider(_settings(search_provider="serper"))
        assert isinstance(provider, SerperProvider)
        assert provider.name == "serper"
