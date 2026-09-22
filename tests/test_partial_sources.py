import pytest

from app.discovery.search import MAX_QUERIES_PER_REQUEST, QueryBuilder
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


class TestQueryPhrasing:
    """What the queries ask for decides what can ever come back."""

    def test_subjects_are_not_quoted(self):
        """A quoted phrase is a hard constraint on Google: "petroleum
        company" cannot match a page calling itself a petroleum *trading*
        company. Quoting the subject was throwing away the near-matches."""
        queries = QueryBuilder().build(DiscoveryRequest(country="Kazakhstan"))
        assert queries
        for q in queries:
            subject = q.split(" Kazakhstan")[0]
            assert '"' not in subject, f"subject should be unquoted: {q!r}"

    def test_multi_word_locations_stay_quoted(self):
        """A place name means the literal place — unquoted, "United Arab
        Emirates" is three loose words."""
        queries = QueryBuilder().build(DiscoveryRequest(country="United Arab Emirates"))
        assert all('"United Arab Emirates"' in q for q in queries)

    def test_a_single_word_location_needs_no_quotes(self):
        queries = QueryBuilder().build(DiscoveryRequest(country="Kazakhstan"))
        assert all('"Kazakhstan"' not in q for q in queries)
        assert all("Kazakhstan" in q for q in queries)

    def test_suppliers_without_a_company_are_searched_for(self):
        """Many suppliers are sole traders whose pages never say "company".
        Every generic phrase containing that word excluded them."""
        queries = QueryBuilder().build(DiscoveryRequest())
        assert queries, "a global search must still produce queries"
        assert any("supplier" in q for q in queries)
        assert any("trader" in q for q in queries)
        assert any("company" not in q for q in queries)

    def test_query_count_is_bounded(self):
        """Every query is a credit, and phrases multiply by locations."""
        request = DiscoveryRequest(
            city="Dubai",
            country="United Arab Emirates",
            region="Middle East",
            products=["diesel", "jet fuel", "gasoil"],
            keywords=["bunkering", "storage"],
        )
        assert len(QueryBuilder().build(request)) <= MAX_QUERIES_PER_REQUEST


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
