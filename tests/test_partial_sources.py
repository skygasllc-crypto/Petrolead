import pytest

from app.discovery.search import (
    MAX_QUERIES_PER_REQUEST,
    SOCIAL_EMAIL_HINT,
    QueryBuilder,
    SearchResultItem,
)
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
        assert any("instagram.com" in q for q in queries)

    def test_social_queries_ask_for_pages_that_show_an_email(self):
        """A social page's snippet is the only thing read from it, so a
        snippet without an email yields no email."""
        request = DiscoveryRequest(country="Nigeria", include_social_search=True)
        queries = QueryBuilder().build_social_queries(request)
        assert all(q.endswith(SOCIAL_EMAIL_HINT) for q in queries)


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


class TestRoleFilter:
    """Asking for suppliers has to actually ask for suppliers."""

    def test_role_combines_with_industry_rather_than_replacing_it(self):
        queries = QueryBuilder().build(
            DiscoveryRequest(industry="Bunkering", role="Suppliers", country="Kazakhstan")
        )
        assert any("bunkering supplier" in q for q in queries)
        # The industry's own phrasing survives alongside it.
        assert any("marine fuel bunkering" in q for q in queries)

    def test_role_phrases_come_first_so_the_cap_cannot_drop_them(self):
        """Queries are capped at 12; if role wording sorted last, choosing a
        role could leave the same company-led queries as before."""
        request = DiscoveryRequest(
            city="Dubai",
            country="United Arab Emirates",
            region="Middle East",
            industry="Petroleum Trading",
            products=["diesel", "jet fuel"],
            role="Suppliers",
        )
        queries = QueryBuilder().build(request)
        assert len(queries) <= MAX_QUERIES_PER_REQUEST
        assert any("supplier" in q for q in queries), "the role must survive truncation"

    def test_role_applies_to_products_too(self):
        queries = QueryBuilder().build(
            DiscoveryRequest(products=["diesel"], role="Distributors")
        )
        assert any("diesel distributor" in q for q in queries)

    def test_role_alone_still_searches_the_trade(self):
        queries = QueryBuilder().build(DiscoveryRequest(role="Traders"))
        assert queries
        assert any("trader" in q for q in queries)

    def test_an_unknown_role_adds_nothing_rather_than_failing(self):
        """A stale client sending a role this build doesn't know must get a
        normal search, not an error or an empty one."""
        queries = QueryBuilder().build(DiscoveryRequest(industry="Refinery", role="Wholesalers"))
        assert queries
        assert all("wholesaler" not in q.lower() for q in queries)

    def test_no_role_leaves_queries_unchanged(self):
        with_none = QueryBuilder().build(DiscoveryRequest(industry="Refinery"))
        with_blank = QueryBuilder().build(DiscoveryRequest(industry="Refinery", role=None))
        assert with_none == with_blank


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
            assert c.social_profiles[0]["platform"] in {"linkedin", "facebook", "instagram"}

    @pytest.mark.asyncio
    async def test_takes_the_email_shown_in_the_snippet(self):
        request = DiscoveryRequest(
            country="United Arab Emirates", include_social_search=True, limit=10,
        )
        candidates = await SocialSource().discover(request)
        assert candidates
        for c in candidates:
            slug = c.source_url.rsplit("/mock-", 1)[1]
            assert [e["email"] for e in c.emails] == [f"info@{slug}.test"]

    @pytest.mark.asyncio
    async def test_real_snippet_emails_and_phones_are_validated(self, monkeypatch):
        class OneHitProvider:
            name = "stub"

            async def search(self, query, *, limit=10):
                return [
                    SearchResultItem(
                        title="Delta Diesel Supply (@deltadiesel) • Instagram photos",
                        url="https://www.instagram.com/deltadiesel/",
                        snippet="AGO & PMS supplier, Lagos. Email: sales@deltadiesel.ng "
                        "Call +234 803 123 4567",
                    )
                ]

        async def fake_mx(email, **_):
            return True

        monkeypatch.setattr("app.discovery.extractor.validate_email_domain", fake_mx)
        request = DiscoveryRequest(country="Nigeria", include_social_search=True, limit=5)
        [candidate] = (await SocialSource(provider=OneHitProvider()).discover(request))[:1]
        assert candidate.website is None
        assert candidate.social_profiles == [
            {"platform": "instagram", "url": "https://www.instagram.com/deltadiesel/"}
        ]
        assert candidate.emails == [{"email": "sales@deltadiesel.ng", "is_valid": True}]
        assert candidate.phones and candidate.phones[0]["is_valid"] is True
