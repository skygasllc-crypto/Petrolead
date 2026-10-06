"""Apollo: looking a LinkedIn profile up by its URL, and a named person by
employer. Apollo is never called — the HTTP layer is replaced so each test
decides what comes back."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.discovery import email_finder
from app.discovery.email_finder import apollo_match, find_person_email
from app.services import company_service

APOLLO = Settings(apollo_api_key="key-not-real")
PROFILE = "https://www.linkedin.com/in/jane-doe-12345"


def _apollo_returns(monkeypatch, payload, *, status=200):
    sent = []

    async def fake_post(self, url, params=None, headers=None, **kwargs):
        sent.append({"url": url, "params": params, "headers": headers})
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return sent


def _person(email="jane.doe@gulfstar.example", status="verified", **extra):
    return {
        "person": {
            "name": "Jane Doe",
            "title": "Head of Crude Trading",
            "email": email,
            "email_status": status,
            "match_confidence": "high",
            "organization": {"name": "Gulfstar Energy", "primary_domain": "gulfstar.example"},
            **extra,
        }
    }


class TestApolloMatch:
    async def test_profile_url_gives_person_employer_and_email(self, monkeypatch):
        sent = _apollo_returns(monkeypatch, _person())
        person = await apollo_match(settings=APOLLO, linkedin_url=PROFILE)
        assert person.name == "Jane Doe"
        assert person.title == "Head of Crude Trading"
        assert person.company_name == "Gulfstar Energy"
        assert person.domain == "gulfstar.example"
        assert person.email == {"email": "jane.doe@gulfstar.example", "is_valid": True}
        assert sent[0]["params"] == {"linkedin_url": PROFILE}
        assert sent[0]["headers"]["x-api-key"] == "key-not-real"

    async def test_guessed_address_is_unconfirmed(self, monkeypatch):
        _apollo_returns(monkeypatch, _person(status="guessed"))
        person = await apollo_match(settings=APOLLO, linkedin_url=PROFILE)
        assert person.email == {"email": "jane.doe@gulfstar.example", "is_valid": None}

    async def test_locked_or_unavailable_address_is_no_address(self, monkeypatch):
        _apollo_returns(monkeypatch, _person(email="email_not_unlocked@domain.com"))
        assert (await apollo_match(settings=APOLLO, linkedin_url=PROFILE)).email is None
        _apollo_returns(monkeypatch, _person(status="unavailable"))
        assert (await apollo_match(settings=APOLLO, linkedin_url=PROFILE)).email is None

    async def test_weak_match_is_no_match(self, monkeypatch):
        _apollo_returns(monkeypatch, _person(match_confidence="low"))
        assert await apollo_match(settings=APOLLO, linkedin_url=PROFILE) is None
        _apollo_returns(monkeypatch, {"person": None})
        assert await apollo_match(settings=APOLLO, linkedin_url=PROFILE) is None

    async def test_rejected_key_is_logged_as_an_error(self, monkeypatch):
        # caplog can't see app loggers (propagation is off), so capture from
        # the logger itself — see tests/test_contact_providers.py.
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture(level=logging.ERROR)
        email_finder.logger.addHandler(handler)
        try:
            _apollo_returns(monkeypatch, {"error": "Invalid access credentials."}, status=401)
            assert await apollo_match(settings=APOLLO, linkedin_url=PROFILE) is None
        finally:
            email_finder.logger.removeHandler(handler)

        messages = [r.getMessage() for r in records]
        assert any("Apollo rejected the API key" in m for m in messages)
        assert not any("key-not-real" in m for m in messages)

    async def test_no_key_no_call(self, monkeypatch):
        sent = _apollo_returns(monkeypatch, _person())
        assert await apollo_match(settings=Settings(), linkedin_url=PROFILE) is None
        assert sent == []

    async def test_contact_provider_apollo_finds_by_name_and_domain(self, monkeypatch):
        sent = _apollo_returns(monkeypatch, _person())
        settings = Settings(contact_provider="apollo", apollo_api_key="key-not-real")
        found = await find_person_email(
            domain="gulfstar.example", full_name="Jane Doe", settings=settings
        )
        assert found == {"email": "jane.doe@gulfstar.example", "is_valid": True}
        assert sent[0]["params"] == {"name": "Jane Doe", "domain": "gulfstar.example"}


class TestLinkedInLookupUsesApollo:
    def test_profile_lookup_returns_apollos_contact(self, client, monkeypatch):
        _apollo_returns(monkeypatch, _person())
        monkeypatch.setattr(company_service, "get_settings", lambda: APOLLO)

        response = client.post("/api/discover-url", json={"url": PROFILE})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["source"] == "apollo"
        assert body["contact_person_name"] == "Jane Doe"
        assert body["company_name"] == "Gulfstar Energy"
        assert body["website"] == "https://gulfstar.example"
        assert body["emails"] == [{"email": "jane.doe@gulfstar.example", "is_valid": True}]

    async def test_no_apollo_match_falls_back(self, db_session, monkeypatch):
        _apollo_returns(monkeypatch, {"person": None})
        preview = await company_service._preview_from_apollo(
            db_session, PROFILE, owner_id="someone", settings=APOLLO
        )
        assert preview is None
