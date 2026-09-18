"""Tests for finding a named person's business email.

Neither Hunter nor Prospeo is ever called: the HTTP layer is replaced so each
test decides exactly what comes back. The interesting cases are the failure
ones — a masked address, a rejected key, an exhausted balance — because those
are what a customer's credit gets spent on if they're mishandled.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from app.config import Settings
from app.discovery import email_finder
from app.discovery.email_finder import find_person_email

PROSPEO = Settings(contact_provider="prospeo", prospeo_api_key="key-not-real")
HUNTER = Settings(contact_provider="hunter", hunter_io_api_key="key-not-real")


def _prospeo_returns(monkeypatch, payload, *, status=200):
    """Answer the enrich-person POST with a fixed payload."""
    sent = []

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        sent.append({"url": url, "json": json, "headers": headers})
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return sent


def _person(email, *, status="VERIFIED", revealed=True):
    return {
        "error": False,
        "person": {"email": {"email": email, "status": status, "revealed": revealed}},
    }


class TestProspeo:
    async def test_a_verified_address_is_returned(self, monkeypatch):
        _prospeo_returns(monkeypatch, _person("jane.doe@gulfstar.example"))
        found = await find_person_email(
            domain="gulfstar.example", full_name="Jane Doe", settings=PROSPEO
        )
        assert found == {"email": "jane.doe@gulfstar.example", "is_valid": True}

    async def test_it_sends_the_documented_request(self, monkeypatch):
        sent = _prospeo_returns(monkeypatch, _person("jane.doe@gulfstar.example"))
        await find_person_email(
            domain="gulfstar.example", full_name="Jane Doe", settings=PROSPEO
        )
        assert sent[0]["headers"]["X-KEY"] == "key-not-real"
        assert sent[0]["json"]["data"] == {
            "first_name": "Jane",
            "last_name": "Doe",
            "company_website": "gulfstar.example",
        }

    async def test_a_masked_address_is_not_a_match(self, monkeypatch):
        """Prospeo masks unrevealed results. Returning one would spend a
        customer's credit on a string that can never be mailed."""
        _prospeo_returns(
            monkeypatch, _person("jane.*****@gulfstar.example", revealed=False)
        )
        assert (
            await find_person_email(
                domain="gulfstar.example", full_name="Jane Doe", settings=PROSPEO
            )
            is None
        )

    async def test_a_masked_address_is_caught_even_if_revealed_is_missing(self, monkeypatch):
        payload = {"error": False, "person": {"email": {"email": "j.*****@x.example"}}}
        _prospeo_returns(monkeypatch, payload)
        assert (
            await find_person_email(domain="x.example", full_name="Jane Doe", settings=PROSPEO)
            is None
        )

    async def test_no_match_is_quiet(self, monkeypatch):
        """A person Prospeo doesn't know is ordinary business. It must not
        log, or a real fault would be buried in the noise of normal misses."""
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture(level=logging.DEBUG)
        email_finder.logger.addHandler(handler)
        try:
            _prospeo_returns(monkeypatch, {"error": True, "error_code": "NO_MATCH"})
            result = await find_person_email(
                domain="gulfstar.example", full_name="Jane Doe", settings=PROSPEO
            )
        finally:
            email_finder.logger.removeHandler(handler)

        assert result is None
        assert records == [], (
            f"NO_MATCH should log nothing, got {[r.getMessage() for r in records]}"
        )

    @pytest.mark.parametrize(
        "code", ["INVALID_DATAPOINTS", "INVALID_REQUEST", "INTERNAL_ERROR", "Rate limit exceeded"]
    )
    async def test_an_unusable_request_is_logged_not_swallowed(self, monkeypatch, code):
        """These mean Prospeo couldn't use what we sent — a broken
        integration, not a missing person. Swallowed, they look identical
        to NO_MATCH and the real fault stays invisible."""
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture(level=logging.WARNING)
        email_finder.logger.addHandler(handler)
        try:
            _prospeo_returns(monkeypatch, {"error": True, "error_code": code})
            result = await find_person_email(
                domain="gulfstar.example", full_name="Jane Doe", settings=PROSPEO
            )
        finally:
            email_finder.logger.removeHandler(handler)

        assert result is None
        assert [r for r in records if r.levelno >= logging.WARNING], "no WARNING was logged"
        assert code in records[0].getMessage()

    @pytest.mark.parametrize("code", ["INVALID_API_KEY", "INSUFFICIENT_CREDITS"])
    async def test_account_failures_are_logged_as_errors(self, monkeypatch, code):
        """A run of NO_MATCH is normal. These mean the integration has
        stopped working, and they must not look the same in the logs.

        caplog can't see these: setup_logging() attaches its own handlers and
        turns off propagation for the petrolead loggers, so records never
        reach pytest's root handler. Capture from the logger itself instead.
        """
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture(level=logging.ERROR)
        email_finder.logger.addHandler(handler)
        try:
            _prospeo_returns(monkeypatch, {"error": True, "error_code": code})
            result = await find_person_email(
                domain="gulfstar.example", full_name="Jane Doe", settings=PROSPEO
            )
        finally:
            email_finder.logger.removeHandler(handler)

        assert result is None
        assert [r for r in records if r.levelno >= logging.ERROR], "no ERROR was logged"
        assert code in records[0].getMessage()

    async def test_a_single_word_name_is_never_sent(self, monkeypatch):
        """Prospeo needs first and last separately; one word can't be split,
        and guessing would burn a credit on a request that cannot match."""
        sent = _prospeo_returns(monkeypatch, _person("x@y.example"))
        assert (
            await find_person_email(domain="y.example", full_name="Cher", settings=PROSPEO)
            is None
        )
        assert sent == []

    async def test_a_network_failure_returns_nothing(self, monkeypatch):
        async def boom(self, url, **kwargs):
            raise httpx.ConnectError("down")

        monkeypatch.setattr(httpx.AsyncClient, "post", boom)
        assert (
            await find_person_email(domain="y.example", full_name="Jane Doe", settings=PROSPEO)
            is None
        )

    async def test_without_a_key_no_request_is_made(self, monkeypatch):
        sent = _prospeo_returns(monkeypatch, _person("x@y.example"))
        settings = Settings(contact_provider="prospeo", prospeo_api_key=None)
        assert (
            await find_person_email(domain="y.example", full_name="Jane Doe", settings=settings)
            is None
        )
        assert sent == []


class TestHunterStillWorks:
    async def test_a_confident_match_is_returned(self, monkeypatch):
        async def fake_get(self, url, params=None, **kwargs):
            payload = {
                "data": {
                    "email": "jane@gulfstar.example",
                    "score": 92,
                    "verification": {"status": "valid"},
                }
            }
            return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        found = await find_person_email(
            domain="gulfstar.example", full_name="Jane Doe", settings=HUNTER
        )
        assert found == {"email": "jane@gulfstar.example", "is_valid": True}

    async def test_a_low_confidence_match_is_refused(self, monkeypatch):
        async def fake_get(self, url, params=None, **kwargs):
            payload = {"data": {"email": "guess@gulfstar.example", "score": 10}}
            return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        assert (
            await find_person_email(
                domain="gulfstar.example", full_name="Jane Doe", settings=HUNTER
            )
            is None
        )


class TestProviderSelection:
    def test_hunter_is_the_default(self):
        assert Settings().contact_provider == "hunter"

    def test_an_unknown_provider_stops_the_app(self):
        with pytest.raises(Exception) as excinfo:
            Settings(contact_provider="clearbit")
        assert "isn't supported" in str(excinfo.value)

    def test_case_and_whitespace_are_forgiven(self):
        assert Settings(contact_provider=" PROSPEO ").contact_provider == "prospeo"

    def test_an_empty_key_is_treated_as_unset(self):
        assert Settings(prospeo_api_key="").prospeo_api_key is None

    async def test_selecting_prospeo_does_not_call_hunter(self, monkeypatch):
        async def fail(self, *args, **kwargs):
            raise AssertionError("Hunter must not be called when Prospeo is selected")

        monkeypatch.setattr(httpx.AsyncClient, "get", fail)
        _prospeo_returns(monkeypatch, {"error": True, "error_code": "NO_MATCH"})
        assert (
            await find_person_email(domain="y.example", full_name="Jane Doe", settings=PROSPEO)
            is None
        )


class TestNameSplitting:
    @pytest.mark.parametrize(
        "full_name,expected",
        [
            ("Jane Doe", ("Jane", "Doe")),
            ("  Jane   Doe  ", ("Jane", "Doe")),
            ("Jane van der Berg", ("Jane", "Berg")),
            ("Cher", None),
            ("", None),
        ],
    )
    def test_names_split_into_first_and_last(self, full_name, expected):
        assert email_finder._split_name(full_name) == expected
