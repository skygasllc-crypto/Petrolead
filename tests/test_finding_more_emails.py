"""Finding more emails: addresses sites hide from bots, more pages per site,
Hunter's domain search, and guessing a person's address from the formats
companies use — kept only when the verification provider confirms it.

No outside service is ever called: HTTP, DNS and the verifier are replaced so
each test decides exactly what comes back.
"""

from __future__ import annotations

import httpx
import pytest
from bs4 import BeautifulSoup

from app.config import Settings
from app.discovery import email_finder, email_verification, extractor
from app.discovery.contacts import find_contact_page, find_extra_pages
from app.discovery.email_finder import (
    candidate_addresses,
    find_domain_emails,
    guess_person_email,
    name_parts,
)
from app.discovery.email_verification import Verdict
from app.discovery.emails import decode_cfemail, extract_emails
from app.discovery.types import DiscoveredCompany
from app.services import company_service


def _cf_encode(address: str, key: int = 0x42) -> str:
    return f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in address)


def _emails_in(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    return extract_emails(soup, soup.get_text(" ", strip=True))


class TestHiddenAddresses:
    def test_cloudflare_attribute_is_decoded(self):
        encoded = _cf_encode("sales@gulfstar.example")
        html = f'<a class="__cf_email__" data-cfemail="{encoded}">[email&#160;protected]</a>'
        assert _emails_in(html) == ["sales@gulfstar.example"]

    def test_cloudflare_link_is_decoded(self):
        encoded = _cf_encode("info@gulfstar.example")
        html = f'<a href="/cdn-cgi/l/email-protection#{encoded}">Email us</a>'
        assert _emails_in(html) == ["info@gulfstar.example"]

    def test_garbage_cloudflare_value_is_ignored(self):
        assert decode_cfemail("zz") is None
        assert decode_cfemail("") is None

    @pytest.mark.parametrize(
        "text",
        [
            "Write to info [at] gulfstar [dot] example",
            "Write to info(at)gulfstar.example",
            "Write to info {at} gulfstar {dot} example",
            "Write to info at gulfstar dot example",
        ],
    )
    def test_spelled_out_addresses_are_rebuilt(self, text):
        assert extract_emails(None, text) == ["info@gulfstar.example"]

    def test_ordinary_english_is_not_an_address(self):
        assert extract_emails(None, "Meet us at noon. Next we visit the yard at dawn.") == []

    def test_structured_data_address_is_found(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type": "Organization", "email": "mailto:trading@gulfstar.example"}'
            "</script>"
        )
        assert _emails_in(html) == ["trading@gulfstar.example"]

    def test_url_encoded_mailto_is_decoded(self):
        assert _emails_in('<a href="mailto:ops%40gulfstar.example">Ops</a>') == [
            "ops@gulfstar.example"
        ]


class TestMorePages:
    HOME = """
    <a href="/contact">Contact</a>
    <a href="/privacy-policy">Privacy</a>
    <a href="/about-us">About us</a>
    <a href="/our-team">Meet the team</a>
    <a href="https://other-site.example/team">Partner team</a>
    <a href="/brochure-team.pdf">Team brochure</a>
    <a href="/">Home</a>
    """

    def _pages(self, limit=5):
        soup = BeautifulSoup(self.HOME, "lxml")
        return find_extra_pages(
            soup,
            "https://gulfstar.example/",
            exclude={"https://gulfstar.example/contact"},
            limit=limit,
        )

    def test_same_site_pages_best_first(self):
        assert self._pages() == [
            "https://gulfstar.example/our-team",
            "https://gulfstar.example/about-us",
            "https://gulfstar.example/privacy-policy",
        ]

    def test_limit_is_respected(self):
        assert self._pages(limit=1) == ["https://gulfstar.example/our-team"]
        assert self._pages(limit=0) == []

    def test_foreign_language_contact_link_is_found(self):
        soup = BeautifulSoup('<a href="/kontakt">Kontakt</a>', "lxml")
        assert find_contact_page(soup, "https://firma.example/") == "https://firma.example/kontakt"

    async def test_website_enrichment_reads_team_page_and_prefers_own_domain(self, monkeypatch):
        pages = {
            "https://gulfstar.example": '<a href="/team">Team</a>'
            "<p>Site by studio@webdesign.example</p>",
            "https://gulfstar.example/team": "<p>Jane Doe, jane.doe@gulfstar.example</p>",
        }
        fetched = []

        async def fake_fetch(client, url):
            fetched.append(url)
            html = pages.get(url.rstrip("/"))
            if html is None:
                return None
            soup = BeautifulSoup(html, "lxml")
            return soup, soup.get_text(" ", strip=True), url

        async def mx_ok(email, **kwargs):
            return True

        monkeypatch.setattr(extractor, "_fetch_page", fake_fetch)
        monkeypatch.setattr(extractor, "validate_email_domain", mx_ok)

        company = DiscoveredCompany(company_name="Gulfstar", website="https://gulfstar.example")
        await extractor.enrich_from_website(company, settings=Settings(website_extra_pages=3))

        assert "https://gulfstar.example/team" in fetched
        assert [e["email"] for e in company.emails] == [
            "jane.doe@gulfstar.example",
            "studio@webdesign.example",
        ]


HUNTER = Settings(hunter_io_api_key="key-not-real", domain_search_enabled=True)


def _hunter_returns(monkeypatch, payload, *, status=200):
    calls = []

    async def fake_get(self, url, params=None, **kwargs):
        calls.append({"url": url, "params": params})
        return httpx.Response(status, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return calls


class TestDomainSearch:
    async def test_confident_addresses_best_first(self, monkeypatch):
        _hunter_returns(
            monkeypatch,
            {
                "data": {
                    "emails": [
                        {"value": "info@gulfstar.example", "confidence": 70},
                        {
                            "value": "jane@gulfstar.example",
                            "confidence": 95,
                            "verification": {"status": "valid"},
                        },
                        {"value": "maybe@gulfstar.example", "confidence": 20},
                        {
                            "value": "gone@gulfstar.example",
                            "confidence": 90,
                            "verification": {"status": "invalid"},
                        },
                    ]
                }
            },
        )
        found = await find_domain_emails(domain="gulfstar.example", settings=HUNTER)
        assert found == [
            {"email": "jane@gulfstar.example", "is_valid": True},
            {"email": "info@gulfstar.example", "is_valid": None},
        ]

    async def test_nothing_without_a_key_or_when_turned_off(self, monkeypatch):
        calls = _hunter_returns(monkeypatch, {"data": {"emails": []}})
        assert await find_domain_emails(domain="g.example", settings=Settings()) == []
        off = Settings(hunter_io_api_key="key-not-real", domain_search_enabled=False)
        assert await find_domain_emails(domain="g.example", settings=off) == []
        assert calls == []

    async def test_a_failed_request_finds_nothing(self, monkeypatch):
        _hunter_returns(monkeypatch, {"errors": [{"id": "no_credits"}]}, status=429)
        assert await find_domain_emails(domain="gulfstar.example", settings=HUNTER) == []

    async def test_only_companies_without_an_email_are_searched_and_capped(self, monkeypatch):
        searched = []

        async def fake_find(*, domain, settings):
            searched.append(domain)
            return [{"email": f"info@{domain}", "is_valid": None}]

        settings = Settings(
            hunter_io_api_key="key-not-real",
            domain_search_enabled=True,
            domain_search_max_per_search=2,
        )
        monkeypatch.setattr(company_service, "get_settings", lambda: settings)
        monkeypatch.setattr(company_service, "find_domain_emails", fake_find)

        has_email = DiscoveredCompany(
            company_name="A",
            website="https://a.example",
            emails=[{"email": "x@a.example", "is_valid": True}],
        )
        social = DiscoveredCompany(company_name="B", website="https://facebook.com/b")
        mock = DiscoveredCompany(company_name="C", website="https://c.example", is_mock=True)
        first = DiscoveredCompany(company_name="D", website="https://www.d.example")
        second = DiscoveredCompany(company_name="E", website="https://e.example")
        third = DiscoveredCompany(company_name="F", website="https://f.example")

        await company_service._add_domain_search_emails(
            [has_email, social, mock, first, second, third]
        )
        assert searched == ["d.example", "e.example"]
        assert first.emails == [{"email": "info@d.example", "is_valid": None}]
        assert third.emails == []


class TestNameFormats:
    def test_titles_accents_and_hyphens_are_cleaned(self):
        assert name_parts("Dr. José García-López, PhD") == ("jose", "garcialopez")

    def test_nickname_in_brackets_is_dropped(self):
        assert name_parts("Robert (Bob) O'Neil") == ("robert", "oneil")

    def test_one_name_is_not_enough(self):
        assert name_parts("Madonna") is None
        assert candidate_addresses("Madonna", "g.example") == []

    def test_most_common_format_first(self):
        addresses = candidate_addresses("Jane Doe", "g.example")
        assert addresses[:4] == [
            "jane.doe@g.example",
            "jane@g.example",
            "jdoe@g.example",
            "janedoe@g.example",
        ]


class _FakeVerifier:
    """Answers from a fixed table; every other address doesn't exist."""

    def __init__(self, answers: dict[str, Verdict]):
        self.answers = answers
        self.checked: list[str] = []

    async def verify(self, addresses):
        self.checked.extend(addresses)
        return {
            a: self.answers.get(a, Verdict(email_verification.UNDELIVERABLE, "mailbox_not_found"))
            for a in addresses
        }


GUESSING = Settings(
    email_verify_provider="millionverifier",
    email_verify_api_key="key-not-real",
    email_guessing_enabled=True,
)


@pytest.fixture()
def verifier(monkeypatch):
    def install(answers=None, *, mx=True):
        fake = _FakeVerifier(answers or {})
        monkeypatch.setattr(email_verification, "get_provider", lambda settings: fake)

        async def fake_mx(email, **kwargs):
            return mx

        monkeypatch.setattr(email_finder, "validate_email_domain", fake_mx)
        return fake

    return install


async def _guess_jane_doe():
    return await guess_person_email(domain="g.example", full_name="Jane Doe", settings=GUESSING)


class TestGuessing:
    async def test_first_confirmed_format_is_returned(self, verifier):
        fake = verifier(
            {"jdoe@g.example": Verdict(email_verification.DELIVERABLE, "mailbox_confirmed")}
        )
        found = await _guess_jane_doe()
        assert found == {"email": "jdoe@g.example", "is_valid": True}
        # A probe, then one batch of three — nothing after the hit.
        assert len(fake.checked) == 4
        assert "janedoe@g.example" not in fake.checked

    async def test_catch_all_domain_is_not_guessed_at(self, verifier):
        fake = verifier()
        fake.answers = _CatchAll()
        found = await _guess_jane_doe()
        assert found is None
        assert len(fake.checked) == 1  # only the probe

    async def test_nothing_confirmed_means_nothing_returned(self, verifier):
        fake = verifier()
        found = await _guess_jane_doe()
        assert found is None
        assert len(fake.checked) == 1 + GUESSING.email_guess_max_checks

    async def test_a_domain_without_mail_costs_nothing(self, verifier):
        fake = verifier(mx=False)
        found = await _guess_jane_doe()
        assert found is None
        assert fake.checked == []

    async def test_off_when_turned_off(self, verifier):
        fake = verifier()
        off = GUESSING.model_copy(update={"email_guessing_enabled": False})
        found = await guess_person_email(domain="g.example", full_name="Jane Doe", settings=off)
        assert found is None
        assert fake.checked == []

    async def test_off_without_a_verification_provider(self):
        # The real get_provider: no key means no provider, so nothing is called.
        dns_only = Settings(email_guessing_enabled=True)
        found = await guess_person_email(
            domain="g.example", full_name="Jane Doe", settings=dns_only
        )
        assert found is None


class _CatchAll(dict):
    def get(self, key, default=None):
        return Verdict(email_verification.RISKY, "catch_all")
