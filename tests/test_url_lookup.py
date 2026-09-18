"""Tests for POST /api/discover-url (the "paste a link" quick lookup).

Monkeypatches `extractor._fetch_page` so these run against canned HTML
instead of a live network fetch — deterministic, and consistent with the
rest of the suite requiring no external services.
"""

from bs4 import BeautifulSoup

from app.discovery import extractor as extractor_module
from app.discovery.search import SearchResultItem
from app.services import company_service
from tests.helpers import discover_url_and_save

HOMEPAGE_HTML = """
<html>
<head>
<title>Falcon Petroleum Trading Co.</title>
<meta name="description" content="A leading petroleum products trading company.">
</head>
<body>
<p>Welcome to Falcon Petroleum Trading, serving the Gulf region since 1998.</p>
<a href="/contact">Contact Us</a>
<a href="mailto:info@falconpetro.example">Email us</a>
<a href="https://linkedin.com/company/falconpetro">LinkedIn</a>
<p>Build 2.3.1000. Reference sequence: 1 1 2 3 5 8 13 21 34 55.</p>
</body>
</html>
"""

CONTACT_HTML = """
<html><head><title>Contact | Falcon Petroleum</title></head>
<body><a href="tel:+971 4 234 5678">Call us</a></body></html>
"""


async def _fake_fetch_page(client, url):
    if url.rstrip("/").endswith("/contact"):
        soup = BeautifulSoup(CONTACT_HTML, "lxml")
        return soup, soup.get_text(" ", strip=True), url
    soup = BeautifulSoup(HOMEPAGE_HTML, "lxml")
    return soup, soup.get_text(" ", strip=True), url


async def _fake_fetch_page_unreachable(client, url):
    return None


class TestDiscoverUrlEndpoint:
    def test_rejects_invalid_url(self, client):
        response = client.post("/api/discover-url", json={"url": "not-a-url"})
        assert response.status_code == 422

    def test_successful_lookup_previews_without_saving(self, client, monkeypatch):
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page)

        response = client.post(
            "/api/discover-url", json={"url": "https://falconpetro.example"}
        )
        assert response.status_code == 200
        body = response.json()

        assert body["company_name"] == "Falcon Petroleum Trading Co."
        # pydantic's AnyHttpUrl normalizes a bare-domain URL with a trailing slash.
        assert body["website"] == "https://falconpetro.example/"
        assert body["contact_page_url"].endswith("/contact")
        assert {"linkedin"} <= {p["platform"] for p in body["social_profiles"]}
        assert any(e["email"] == "info@falconpetro.example" for e in body["emails"])
        assert body["already_saved"] is False
        assert body["existing_company_id"] is None
        assert "id" not in body  # not persisted yet

        # The tel: link on the contact page is trusted and surfaced...
        phones = {p["phone"] for p in body["phones"]}
        assert any("971" in p or "234" in p for p in phones)
        # ...but plaintext numeric noise (a founding year, a build number,
        # a Fibonacci-looking sequence) must never be surfaced as a phone.
        assert "1998" not in phones
        assert not any("1000" in p for p in phones)

        # And nothing was saved to the database from the preview alone.
        assert client.get("/api/companies").json()["total"] == 0

    def test_lookup_then_save_creates_a_real_company(self, client, monkeypatch):
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page)

        _, saved = discover_url_and_save(client, "https://falconpetro.example")
        company_id = saved["id"]

        listed = client.get("/api/companies").json()
        assert any(c["id"] == company_id for c in listed["items"])

    def test_unreachable_or_login_gated_page_returns_clear_422(self, client, monkeypatch):
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page_unreachable)

        response = client.post(
            "/api/discover-url", json={"url": "https://www.linkedin.com/company/example"}
        )
        assert response.status_code == 422
        assert "login-gated" in response.json()["detail"]

    def test_relookup_of_same_domain_merges_not_duplicates(self, client, monkeypatch):
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page)

        _, first_saved = discover_url_and_save(client, "https://falconpetro.example")

        second_preview = client.post(
            "/api/discover-url", json={"url": "https://falconpetro.example/"}
        ).json()
        assert second_preview["already_saved"] is True
        assert second_preview["existing_company_id"] == first_saved["id"]

        second_save = client.post("/api/companies/save", json=second_preview)
        assert second_save.json()["id"] == first_saved["id"]


class TestPersonalProfileUrlFallback:
    """A personal LinkedIn profile URL (`/in/...`) is login-gated and never
    fetched directly — it's routed to a search-snippet fallback instead
    (`app.discovery.profile_lookup`). These exercise that path end to end
    against the mock search provider (`tests/conftest.py` defaults
    `SEARCH_PROVIDER=mock`), which synthesizes a clearly-labeled
    name/title/company snippet for exactly this scenario.
    """

    def test_linkedin_profile_url_previews_contact_person_and_company(self, client):
        response = client.post(
            "/api/discover-url", json={"url": "https://ca.linkedin.com/in/michaellwjones"}
        )
        assert response.status_code == 200
        body = response.json()

        assert body["contact_person_name"]
        assert "Michaellwjones" in body["contact_person_name"]
        assert body["contact_person_title"] == "Senior Trading Manager"
        assert body["company_name"]
        assert body["is_mock"] is True
        assert {"linkedin"} <= {p["platform"] for p in body["social_profiles"]}
        assert "id" not in body  # preview only, not saved

    def test_linkedin_company_page_url_is_not_routed_to_profile_fallback(self, client, monkeypatch):
        # /company/ URLs are business pages, not personal profiles — they
        # still go through the normal website-fetch path (and fail there,
        # since that path is also login-gated), never the snippet fallback.
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page_unreachable)
        response = client.post(
            "/api/discover-url", json={"url": "https://www.linkedin.com/company/example"}
        )
        assert response.status_code == 422

    def test_saving_a_profile_snippet_preview_creates_a_company_with_contact_person(self, client):
        preview = client.post(
            "/api/discover-url", json={"url": "https://linkedin.com/in/jane-doe"}
        ).json()
        save_response = client.post("/api/companies/save", json=preview)
        assert save_response.status_code == 200
        saved = save_response.json()
        assert saved["company_name"] == preview["company_name"]

        detail = client.get(f"/api/companies/{saved['id']}").json()
        assert detail["contact"]["contact_person_name"] == preview["contact_person_name"]
        assert detail["contact"]["contact_person_title"] == preview["contact_person_title"]


class _FakeRealProvider:
    """A non-mock provider stand-in — the Hunter.io enrichment path is
    deliberately skipped for the mock provider (see
    `company_service._preview_from_profile_snippet`), so exercising it
    needs something with a different `.name`."""

    name = "fake_real_provider"

    def __init__(self, snippet_title: str, website_url: str | None):
        self._snippet_title = snippet_title
        self._website_url = website_url

    async def search(self, query, *, limit=10):
        if "linkedin.com/in/" in query:
            return [SearchResultItem(title=self._snippet_title, url="https://linkedin.com/in/x")]
        if "official website" in query and self._website_url:
            return [SearchResultItem(title="Official site", url=self._website_url)]
        return []


class TestProfileSnippetFailureMessages:
    """A profile lookup fails only when there's no usable public listing at
    all. A person whose listing names no employer is still a result."""

    def test_profile_found_without_employer_still_returns_the_person(self, client, monkeypatch):
        """The listing names no current employer, so there's no company and
        no domain to find an email against — but the customer still gets who
        the person is, and is charged nothing for it."""
        fake_provider = _FakeRealProvider(
            snippet_title="Bill Gates - Chair, Gates Foundation and Founder, Breakthrough ...",
            website_url=None,
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        response = client.post(
            "/api/discover-url", json={"url": "https://www.linkedin.com/in/williamhgates"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["contact_person_name"] == "Bill Gates"
        assert body["company_name"] is None
        assert body["emails"] == []
        assert body["social_profiles"] == [
            {"platform": "linkedin", "url": "https://www.linkedin.com/in/williamhgates"}
        ]

    def test_profile_with_no_search_listing(self, client, monkeypatch):
        class _NoResults(_FakeRealProvider):
            async def search(self, query, *, limit=10):
                return []

        monkeypatch.setattr(
            company_service, "get_search_provider", lambda settings: _NoResults("", None)
        )
        response = client.post("/api/discover-url", json={"url": "https://linkedin.com/in/nobody"})
        assert response.status_code == 422
        assert "No public search listing" in response.json()["detail"]


class TestProfileSnippetEmailEnrichment:
    """The optional Hunter.io enrichment on top of the profile-snippet
    fallback: once a company's domain is resolved via an actual search
    result, try to attach a verified business email for the named person.
    Best-effort throughout — never blocks the preview from succeeding."""

    def test_enriches_with_a_found_email_when_hunter_has_a_confident_match(
        self, client, monkeypatch
    ):
        fake_provider = _FakeRealProvider(
            snippet_title="Michael Jones - Senior Trading Manager at Falcon Petroleum "
            "Trading | LinkedIn",
            website_url="https://falconpetro.example/about",
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        async def fake_find_person_email(*, domain, full_name, settings):
            assert domain == "falconpetro.example"
            assert full_name == "Michael Jones"
            return {"email": "michael.jones@falconpetro.example", "is_valid": True}

        monkeypatch.setattr(company_service, "find_person_email", fake_find_person_email)

        response = client.post(
            "/api/discover-url", json={"url": "https://linkedin.com/in/michaeljones"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["website"] == "https://falconpetro.example"
        assert body["emails"] == [
            {"email": "michael.jones@falconpetro.example", "is_valid": True}
        ]

    def test_contact_is_returned_even_when_no_email_matches(self, client, monkeypatch):
        """The provider had no confident match. The person, their title and
        their employer's website are still worth returning; only the email
        is missing, and only an email costs a credit."""
        fake_provider = _FakeRealProvider(
            snippet_title="Michael Jones - Senior Trading Manager at Falcon Petroleum "
            "Trading | LinkedIn",
            website_url="https://falconpetro.example/about",
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        async def fake_find_person_email(*, domain, full_name, settings):
            return None

        monkeypatch.setattr(company_service, "find_person_email", fake_find_person_email)

        response = client.post(
            "/api/discover-url", json={"url": "https://linkedin.com/in/michaeljones"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["contact_person_name"] == "Michael Jones"
        assert body["company_name"] == "Falcon Petroleum Trading"
        assert body["website"] == "https://falconpetro.example"
        assert body["emails"] == []

    def test_no_domain_found_skips_enrichment_entirely(self, client, monkeypatch):
        fake_provider = _FakeRealProvider(
            snippet_title="Michael Jones - Senior Trading Manager at Falcon Petroleum "
            "Trading | LinkedIn",
            website_url=None,
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        called = False

        async def fake_find_person_email(*, domain, full_name, settings):
            nonlocal called
            called = True
            return None

        monkeypatch.setattr(company_service, "find_person_email", fake_find_person_email)

        response = client.post(
            "/api/discover-url", json={"url": "https://linkedin.com/in/michaeljones"}
        )
        # No domain means nothing to look an email up against, so the
        # provider is never called — but the contact still comes back.
        assert response.status_code == 200
        body = response.json()
        assert body["company_name"] == "Falcon Petroleum Trading"
        assert body["website"] is None
        assert body["emails"] == []
        assert called is False

    def test_blocked_domains_are_never_used_as_the_company_website(self, client, monkeypatch):
        # A search hit for the person's own LinkedIn/company page must
        # never be mistaken for the company's own website domain.
        fake_provider = _FakeRealProvider(
            snippet_title="Michael Jones - Senior Trading Manager at Falcon Petroleum "
            "Trading | LinkedIn",
            website_url="https://linkedin.com/company/falcon-petroleum",
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        async def fail_if_called(*, domain, full_name, settings):
            raise AssertionError("find_person_email must not be called without a resolved domain")

        monkeypatch.setattr(company_service, "find_person_email", fail_if_called)

        response = client.post(
            "/api/discover-url", json={"url": "https://linkedin.com/in/michaeljones"}
        )
        # The blocked hit yields no usable domain, so no email lookup runs
        # (enforced by fail_if_called above) and no website is claimed — but
        # the contact itself is still returned.
        assert response.status_code == 200
        body = response.json()
        assert body["contact_person_name"] == "Michael Jones"
        assert body["website"] is None
        assert body["emails"] == []
