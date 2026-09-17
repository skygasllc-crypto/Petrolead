"""Tests for mailbox-level verification via an external provider.

These never call MillionVerifier. The HTTP layer is replaced so each test
decides exactly what the provider returns — including its failure modes,
which are the interesting part: a provider outage must degrade to "we
couldn't check" rather than discarding a batch or failing the request.

Their documented test key returns *random* results, so it is deliberately
not used here; a flaky test is worse than no test.
"""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.discovery import email_verification as verification
from app.discovery.email_verification import MillionVerifierProvider, get_provider

KEY = "test-key-not-a-real-one"


def _responder(monkeypatch, by_email):
    """Answer each request from a table of {email: payload-or-exception}."""
    calls = []

    async def fake_get(self, url, params=None, **kwargs):
        address = params["email"]
        calls.append(address)
        outcome = by_email[address]
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(200, json=outcome, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return calls


class TestResultMapping:
    @pytest.mark.parametrize(
        "result,status,reason",
        [
            ("ok", "deliverable", "mailbox_confirmed"),
            ("invalid", "undeliverable", "mailbox_not_found"),
            ("disposable", "undeliverable", "disposable_domain"),
            ("catch_all", "risky", "catch_all"),
            ("unknown", "unknown", "provider_error"),
        ],
    )
    async def test_each_provider_result_maps_to_a_verdict(
        self, monkeypatch, result, status, reason
    ):
        _responder(monkeypatch, {"a@x.example": {"result": result}})
        verdicts = await MillionVerifierProvider(KEY).verify(["a@x.example"])
        assert verdicts["a@x.example"].status == status
        assert verdicts["a@x.example"].reason == reason

    async def test_catch_all_is_never_deliverable(self, monkeypatch):
        """The server accepts everything, so acceptance proves nothing —
        calling it deliverable is how a verified list still bounces."""
        _responder(monkeypatch, {"a@x.example": {"result": "catch_all"}})
        verdicts = await MillionVerifierProvider(KEY).verify(["a@x.example"])
        assert verdicts["a@x.example"].status != "deliverable"

    async def test_a_confirmed_role_inbox_is_downgraded(self, monkeypatch):
        _responder(monkeypatch, {"info@x.example": {"result": "ok", "role": True}})
        verdicts = await MillionVerifierProvider(KEY).verify(["info@x.example"])
        assert verdicts["info@x.example"].status == "risky"
        assert verdicts["info@x.example"].reason == "role_account"

    async def test_an_unrecognised_result_is_unknown_not_deliverable(self, monkeypatch):
        _responder(monkeypatch, {"a@x.example": {"result": "something_new"}})
        verdicts = await MillionVerifierProvider(KEY).verify(["a@x.example"])
        assert verdicts["a@x.example"].status == "unknown"


class TestFailureHandling:
    async def test_a_network_error_marks_only_that_address_unknown(self, monkeypatch):
        _responder(
            monkeypatch,
            {
                "good@x.example": {"result": "ok"},
                "broken@x.example": httpx.ConnectError("boom"),
            },
        )
        verdicts = await MillionVerifierProvider(KEY).verify(
            ["good@x.example", "broken@x.example"]
        )
        assert verdicts["good@x.example"].status == "deliverable"
        assert verdicts["broken@x.example"].status == "unknown"

    async def test_an_error_field_in_the_payload_is_respected(self, monkeypatch):
        _responder(monkeypatch, {"a@x.example": {"error": "insufficient credits"}})
        verdicts = await MillionVerifierProvider(KEY).verify(["a@x.example"])
        assert verdicts["a@x.example"].status == "unknown"


class TestProviderSelection:
    def test_mx_means_no_provider(self):
        assert get_provider(Settings(email_verify_provider="mx")) is None

    def test_a_provider_without_a_key_is_not_used(self):
        """Without credentials it could only fail every address; saying
        nothing was checked is more honest than reporting all unknown."""
        settings = Settings(email_verify_provider="millionverifier", email_verify_api_key=None)
        assert get_provider(settings) is None

    def test_a_configured_provider_is_returned(self):
        settings = Settings(email_verify_provider="millionverifier", email_verify_api_key=KEY)
        provider = get_provider(settings)
        assert isinstance(provider, MillionVerifierProvider)

    def test_the_config_now_accepts_the_provider_name(self):
        assert "millionverifier" in verification._PROVIDERS
