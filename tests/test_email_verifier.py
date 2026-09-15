"""Tests for the Email Verifier: address syntax checks and POST /api/emails/verify.

The MX lookup is monkeypatched so these never touch real DNS.
"""

import pytest

from app.discovery import emails as emails_module
from app.discovery.emails import is_valid_email_syntax
from app.schemas import MAX_VERIFY_EMAILS


def _fake_mx(results_by_domain):
    async def fake_validate_email_domain(email, *, timeout=3.0):
        return results_by_domain[email.rsplit("@", 1)[-1]]

    return fake_validate_email_domain


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

        assert [r["status"] for r in body["results"]] == [
            "valid",
            "no_mail_server",
            "unknown",
            "invalid_format",
        ]
        assert body["results"][0]["domain_accepts_mail"] is True
        assert body["results"][2]["domain_accepts_mail"] is None
        assert body["results"][3]["syntax_valid"] is False
        assert body["valid_count"] == 1
        assert body["invalid_count"] == 2
        assert body["unknown_count"] == 1

    def test_malformed_address_never_triggers_a_dns_lookup(self, client, monkeypatch):
        async def fail_if_called(*args, **kwargs):
            raise AssertionError("no MX lookup should run for a malformed address")

        monkeypatch.setattr(emails_module, "validate_email_domain", fail_if_called)

        response = client.post("/api/emails/verify", json={"emails": ["jane@"]})
        assert response.status_code == 200
        assert response.json()["results"][0]["status"] == "invalid_format"

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
