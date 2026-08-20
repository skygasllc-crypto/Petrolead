import pytest

from app.discovery.search import QueryBuilder
from app.discovery.sources import B2BSource, SocialSource
from app.discovery.types import DiscoveryRequest


class TestQueryBuilderB2BAndSocial:
    def test_b2b_queries_empty_when_not_requested(self):
        request = DiscoveryRequest(country="United Arab Emirates", include_b2b_directories=False)
        assert QueryBuilder().build_b2b_directory_queries(request) == []

    def test_b2b_queries_scoped_with_site_operator(self):
        request = DiscoveryRequest(
            country="United Arab Emirates", industry="Petroleum Trading",
            include_b2b_directories=True,
        )
        queries = QueryBuilder().build_b2b_directory_queries(request)
        assert len(queries) > 0
        assert all(q.startswith("site:") for q in queries)
        assert any("tradekey.com" in q for q in queries)

    def test_social_queries_empty_when_not_requested(self):
        request = DiscoveryRequest(country="United Arab Emirates", include_social_search=False)
        assert QueryBuilder().build_social_queries(request) == []

    def test_social_queries_scoped_with_site_operator(self):
        request = DiscoveryRequest(
            country="United Arab Emirates", industry="Petroleum Trading",
            include_social_search=True,
        )
        queries = QueryBuilder().build_social_queries(request)
        assert len(queries) > 0
        assert any("linkedin.com" in q for q in queries)
        assert any("facebook.com" in q for q in queries)


class TestB2BSource:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        request = DiscoveryRequest(country="United Arab Emirates", limit=10)
        assert await B2BSource().discover(request) == []

    @pytest.mark.asyncio
    async def test_candidates_never_carry_a_website(self):
        request = DiscoveryRequest(
            country="United Arab Emirates", industry="Petroleum Trading",
            include_b2b_directories=True, limit=10,
        )
        candidates = await B2BSource().discover(request)
        assert len(candidates) > 0
        assert all(c.website is None for c in candidates)
        assert all(c.source.startswith("b2b_directory:") for c in candidates)
        assert all(c.source_url for c in candidates)


class TestSocialSource:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        request = DiscoveryRequest(country="United Arab Emirates", limit=10)
        assert await SocialSource().discover(request) == []

    @pytest.mark.asyncio
    async def test_candidates_never_carry_a_website_and_record_social_profile(self):
        request = DiscoveryRequest(
            country="United Arab Emirates", industry="Petroleum Trading",
            include_social_search=True, limit=10,
        )
        candidates = await SocialSource().discover(request)
        assert len(candidates) > 0
        for c in candidates:
            assert c.website is None
            assert len(c.social_profiles) == 1
            assert c.social_profiles[0]["platform"] in {"linkedin", "facebook"}
