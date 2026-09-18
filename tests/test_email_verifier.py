"""Tests for the Email Verifier: address syntax checks and POST /api/emails/verify.

The MX lookup is monkeypatched so these never touch real DNS.
"""

import asyncio

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.discovery import email_verification as verification
from app.discovery import emails as emails_module
from app.discovery.emails import is_valid_email_syntax
from app.schemas import MAX_VERIFY_EMAILS


def _fake_mx(results_by_domain):
    async def fake_validate_email_domain(email, *, timeout=3.0):
        return results_by_domain[email.rsplit("@", 1)[-1]]

    return fake_validate_email_domain


class TestVerificationProviderSetting:
    """An unimplemented provider must stop the app, not quietly fall back to
    DNS-only — the symptom of that fallback is bounced customer mail."""

    def test_the_default_is_accepted(self):
        assert Settings(email_verify_provider="mx").email_verify_provider == "mx"

    def test_case_and_whitespace_are_forgiven(self):
        assert Settings(email_verify_provider=" MX ").email_verify_provider == "mx"

    def test_a_provider_without_an_adapter_is_refused(self):
        with pytest.raises(ValidationError) as excinfo:
            Settings(email_verify_provider="zerobounce")
        assert "has no adapter yet" in str(excinfo.value)

    def test_an_empty_api_key_is_treated_as_unset(self):
        assert Settings(email_verify_api_key="").email_verify_api_key is None


class TestEmailSyntax:
    @pytest.mark.parametrize(
        "email",
        [
            "jane.doe@gulfstar.example",
            "sales+eu@rhine-petro.de",
            "a@b.co",
            "ops@mail.harbor.com.sg",
        ],
    )
    def test_accepts_well_formed_addresses(self, email):
        assert is_valid_email_syntax(email)

    @pytest.mark.parametrize(
        "email",
        [
            "",
            "no-at-sign.com",
            "two@@signs.com",
            "jane@",
            "@gulfstar.com",
            "jane@gulfstar",
            "jane..doe@gulfstar.com",
            ".jane@gulfstar.com",
            "jane.@gulfstar.com",
            "jane@-gulfstar.com",
            "jane doe@gulfstar.com",
            "a" * 65 + "@gulfstar.com",
        ],
    )
    def test_rejects_malformed_addresses(self, email):
        assert not is_valid_email_syntax(email)


class TestVerifyEmailsEndpoint:
    def test_reports_each_status_with_counts(self, client, monkeypatch):
        monkeypatch.setattr(
            emails_module,
            "validate_email_domain",
            _fake_mx(
                {"gulfstar.example": True, "dead-domain.example": False, "flaky.example": None}
            ),
        )

        response = client.post(
            "/api/emails/verify",
            json={
                "emails": [
                    "jane@gulfstar.example",
                    "bob@dead-domain.example",
                    "amy@flaky.example",
                    "not-an-email",
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()

        # Without a verification provider the live domain is "risky", not
        # "deliverable": nothing checked whether that mailbox exists.
        assert [r["status"] for r in body["results"]] == [
            "risky",
            "undeliverable",
            "unknown",
            "undeliverable",
        ]
        assert [r["reason"] for r in body["results"]] == [
            "domain_only",
            "no_mail_server",
            "dns_error",
            "invalid_format",
        ]
        assert body["results"][0]["domain_accepts_mail"] is True
        assert body["results"][2]["domain_accepts_mail"] is None
        assert body["results"][3]["syntax_valid"] is False
        assert body["deliverable_count"] == 0
        assert body["risky_count"] == 1
        assert body["undeliverable_count"] == 2
        assert body["unknown_count"] == 1
        assert body["mailbox_checks_available"] is False

    def test_malformed_address_never_triggers_a_dns_lookup(self, client, monkeypatch):
        async def fail_if_called(*args, **kwargs):
            raise AssertionError("no MX lookup should run for a malformed address")

        monkeypatch.setattr(emails_module, "validate_email_domain", fail_if_called)

        response = client.post("/api/emails/verify", json={"emails": ["jane@"]})
        assert response.status_code == 200
        assert response.json()["results"][0]["status"] == "undeliverable"
        assert response.json()["results"][0]["reason"] == "invalid_format"

    def test_throwaway_and_misspelled_domains_are_undeliverable_without_dns(
        self, client, monkeypatch
    ):
        """Bounces we can name for free — and they must not cost a lookup."""

        async def fail_if_called(*args, **kwargs):
            raise AssertionError("no MX lookup should run for a screened address")

        monkeypatch.setattr(emails_module, "validate_email_domain", fail_if_called)

        response = client.post(
            "/api/emails/verify",
            json={"emails": ["someone@mailinator.com", "jane@gmial.com"]},
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert [r["status"] for r in results] == ["undeliverable", "undeliverable"]
        assert [r["reason"] for r in results] == ["disposable_domain", "typo_suspected"]

    def test_unconfirmed_shared_inboxes_stay_risky(self, client, monkeypatch):
        """No provider is configured here, so nothing checked the mailbox.
        A confirmed shared inbox IS deliverable (see the provider tests) —
        but only once something confirmed it. This is the unconfirmed case
        and it must stay risky."""
        monkeypatch.setattr(
            emails_module, "validate_email_domain", _fake_mx({"gulfstar.example": True})
        )

        response = client.post(
            "/api/emails/verify",
            json={"emails": ["info@gulfstar.example", "jane@gulfstar.example"]},
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert [r["reason"] for r in results] == ["role_account", "domain_only"]
        assert all(r["status"] == "risky" for r in results)

    def test_drops_blanks_and_case_insensitive_duplicates(self, client, monkeypatch):
        monkeypatch.setattr(
            emails_module, "validate_email_domain", _fake_mx({"gulfstar.example": True})
        )

        response = client.post(
            "/api/emails/verify",
            json={
                "emails": [
                    "  jane@gulfstar.example ",
                    "JANE@gulfstar.example",
                    "",
                    "bob@gulfstar.example",
                ]
            },
        )
        assert response.status_code == 200
        assert [r["email"] for r in response.json()["results"]] == [
            "jane@gulfstar.example",
            "bob@gulfstar.example",
        ]

    def test_one_lookup_per_domain_not_per_address(self, client, monkeypatch):
        """The point of the batch layer: an MX record belongs to the domain,
        so 500 addresses at one company must not cost 500 DNS queries."""
        looked_up: list[str] = []

        async def counting_validate(email, *, timeout=3.0):
            looked_up.append(email.rsplit("@", 1)[-1])
            return True

        monkeypatch.setattr(emails_module, "validate_email_domain", counting_validate)

        response = client.post(
            "/api/emails/verify",
            json={
                "emails": [
                    "a@gulfstar.example",
                    "b@gulfstar.example",
                    "c@gulfstar.example",
                    "d@rhine-petro.example",
                    "e@rhine-petro.example",
                ]
            },
        )
        assert response.status_code == 200
        assert sorted(looked_up) == ["gulfstar.example", "rhine-petro.example"]
        assert len(response.json()["results"]) == 5
        assert all(r["status"] == "risky" for r in response.json()["results"])

    def test_a_full_batch_of_the_maximum_is_accepted(self, client, monkeypatch):
        monkeypatch.setattr(
            emails_module, "validate_email_domain", _fake_mx({"gulfstar.example": True})
        )
        emails = [f"person{i}@gulfstar.example" for i in range(MAX_VERIFY_EMAILS)]

        response = client.post("/api/emails/verify", json={"emails": emails})
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == MAX_VERIFY_EMAILS
        # The MX provider can't confirm mailboxes, so a full batch of live
        # addresses is risky, not deliverable.
        assert body["risky_count"] == MAX_VERIFY_EMAILS
        assert body["deliverable_count"] == 0

    def test_domains_that_run_out_of_budget_are_unknown_not_invalid(self, client, monkeypatch):
        """A slow resolver must degrade to "couldn't check" rather than
        holding the request open or calling a good address invalid."""

        async def never_answers(email, *, timeout=3.0):
            await asyncio.sleep(5)
            return True

        monkeypatch.setattr(emails_module, "validate_email_domain", never_answers)
        monkeypatch.setattr(emails_module, "BATCH_BUDGET_SECONDS", 0.05)

        response = client.post(
            "/api/emails/verify", json={"emails": ["jane@slow-dns.example"]}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["results"][0]["status"] == "unknown"
        assert body["results"][0]["domain_accepts_mail"] is None
        assert body["unknown_count"] == 1

    def test_a_provider_that_cannot_decide_falls_back_to_dns(self, client, monkeypatch):
        """A provider outage must degrade to domain-only grading, never below
        it. Reporting every address as uncheckable is worse than the answer
        we could give without any provider at all."""

        class DeadProvider:
            async def verify(self, addresses):
                return {
                    a: verification.Verdict(verification.UNKNOWN, "provider_error")
                    for a in addresses
                }

        monkeypatch.setattr(verification, "get_provider", lambda settings: DeadProvider())
        monkeypatch.setattr(
            emails_module, "validate_email_domain", _fake_mx({"gulfstar.example": True})
        )

        response = client.post(
            "/api/emails/verify", json={"emails": ["jane@gulfstar.example"]}
        )
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["status"] == "risky"
        assert result["reason"] == "domain_only"

    def test_rejects_an_empty_list(self, client):
        response = client.post("/api/emails/verify", json={"emails": []})
        assert response.status_code == 422

    def test_rejects_more_than_the_maximum(self, client):
        emails = [f"person{i}@gulfstar.example" for i in range(MAX_VERIFY_EMAILS + 1)]
        response = client.post("/api/emails/verify", json={"emails": emails})
        assert response.status_code == 422

    def test_requires_login(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/emails/verify", json={"emails": ["jane@gulfstar.example"]}
        )
        assert response.status_code == 401
