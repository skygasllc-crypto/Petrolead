"""Tests for the hardening measures: SSRF blocking, rate limiting,
security headers, login timing and whether the API docs are served.

The rate-limiting tests switch the limiter back on (conftest turns it off
for the suite as a whole) the same way the billing tests switch enforcement
on: by patching the settings the middleware reads.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.config import get_settings as real_get_settings
from app.core import middleware as middleware_module
from app.core import net_guard
from app.core.net_guard import BlockedURLError, assert_public_url

PASSWORD = "correct-horse-battery"


def _fake_dns(monkeypatch, mapping: dict[str, list[str]]):
    """Resolve names from a table instead of the network, so these tests
    never depend on DNS or reach anything real."""

    async def fake_resolve(host: str, port: int) -> list[str]:
        if host not in mapping:
            raise OSError(f"unknown host {host}")
        return mapping[host]

    monkeypatch.setattr(net_guard, "_resolve_ips", fake_resolve)


class TestSsrfGuard:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:8000/api/admin/users",  # this API
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://10.1.2.3/",  # RFC1918
            "http://192.168.0.1/admin",
            "http://172.16.5.4/",
            "http://[::1]/",  # IPv6 loopback
        ],
    )
    async def test_private_addresses_are_refused(self, url):
        with pytest.raises(BlockedURLError):
            await assert_public_url(url)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://x/"])
    async def test_only_http_and_https_are_fetched(self, url):
        with pytest.raises(BlockedURLError):
            await assert_public_url(url)

    @pytest.mark.asyncio
    async def test_a_public_address_is_allowed(self, monkeypatch):
        _fake_dns(monkeypatch, {"example.com": ["93.184.216.34"]})
        await assert_public_url("https://example.com/about")

    @pytest.mark.asyncio
    async def test_a_name_resolving_to_a_private_address_is_refused(self, monkeypatch):
        # The standard way past a naive check: a public-looking hostname with
        # a private A record.
        _fake_dns(monkeypatch, {"internal.example.com": ["127.0.0.1"]})
        with pytest.raises(BlockedURLError):
            await assert_public_url("https://internal.example.com/")

    @pytest.mark.asyncio
    async def test_one_private_address_among_several_is_enough_to_refuse(self, monkeypatch):
        _fake_dns(monkeypatch, {"mixed.example.com": ["93.184.216.34", "10.0.0.5"]})
        with pytest.raises(BlockedURLError):
            await assert_public_url("https://mixed.example.com/")

    @pytest.mark.asyncio
    async def test_a_name_that_does_not_resolve_is_refused(self, monkeypatch):
        _fake_dns(monkeypatch, {})
        with pytest.raises(BlockedURLError):
            await assert_public_url("https://nowhere.example.com/")


class TestRateLimiting:
    @pytest.fixture(autouse=True)
    def _limit(self, monkeypatch):
        settings = real_get_settings().model_copy(
            update={"rate_limit_enabled": True, "auth_rate_limit_per_minute": 3,
                    "rate_limit_per_minute": 5}
        )
        monkeypatch.setattr(middleware_module, "get_settings", lambda: settings)
        middleware_module.reset_rate_limits()
        yield
        middleware_module.reset_rate_limits()

    def test_repeated_failed_logins_are_throttled(self, unauthenticated_client):
        body = {"email": "nobody@example.com", "password": "wrong-password-here"}
        for _ in range(3):
            assert unauthenticated_client.post("/api/auth/login", json=body).status_code == 401

        blocked = unauthenticated_client.post("/api/auth/login", json=body)
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
        assert "Too many requests" in blocked.json()["detail"]

    def test_ordinary_endpoints_have_their_own_larger_allowance(self, unauthenticated_client):
        # The auth allowance is 3 here; health should still answer a 4th time.
        for _ in range(4):
            assert unauthenticated_client.get("/api/health").status_code == 200

    def test_the_limit_is_per_client_address(self, unauthenticated_client):
        body = {"email": "nobody@example.com", "password": "wrong-password-here"}
        for _ in range(4):
            unauthenticated_client.post("/api/auth/login", json=body)

        # A different address gets its own window.
        fresh = unauthenticated_client.post(
            "/api/auth/login", json=body, headers={"x-forwarded-for": "203.0.113.9"}
        )
        # Not trusted by default, so the forged header changes nothing.
        assert fresh.status_code == 429

    def test_forwarded_header_is_used_only_when_proxies_are_trusted(self, monkeypatch):
        from starlette.requests import Request

        def request_from(headers, client_host="10.0.0.1"):
            scope = {
                "type": "http",
                "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
                "client": (client_host, 1234),
            }
            return Request(scope)

        untrusting = Settings(secret_key="x" * 32, trust_proxy_headers=False)
        trusting = Settings(secret_key="x" * 32, trust_proxy_headers=True)
        request = request_from({"x-forwarded-for": "203.0.113.9, 10.0.0.1"})

        assert middleware_module.client_key(request, untrusting) == "10.0.0.1"
        assert middleware_module.client_key(request, trusting) == "203.0.113.9"


class TestSecurityHeaders:
    def test_responses_carry_the_hardening_headers(self, unauthenticated_client):
        headers = unauthenticated_client.get("/api/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

    def test_hsts_is_only_sent_outside_development(self, unauthenticated_client, monkeypatch):
        assert "Strict-Transport-Security" not in unauthenticated_client.get("/api/health").headers

        production = real_get_settings().model_copy(
            update={"app_env": "production", "secret_key": "x" * 32}
        )
        monkeypatch.setattr(middleware_module, "get_settings", lambda: production)
        headers = unauthenticated_client.get("/api/health").headers
        assert "max-age=31536000" in headers["Strict-Transport-Security"]


class TestDocsExposure:
    def test_docs_are_served_in_development(self):
        assert Settings(app_env="development").serve_docs is True

    def test_docs_are_not_served_in_production(self):
        assert Settings(app_env="production", secret_key="x" * 32).serve_docs is False

    def test_an_explicit_setting_wins(self):
        assert Settings(app_env="production", secret_key="x" * 32, docs_enabled=True).serve_docs
        assert Settings(app_env="development", docs_enabled=False).serve_docs is False

    def test_an_empty_value_is_treated_as_unset(self):
        # A copied .env.example, or an empty field in a platform dashboard,
        # sends "" — which must not stop the app from booting at all.
        assert Settings(app_env="development", docs_enabled="").serve_docs is True


class TestLoginDoesNotLeakWhichEmailsExist:
    def test_unknown_email_is_still_password_checked(self, unauthenticated_client, monkeypatch):
        """The check has to happen for an address with no account too, or the
        response time gives the answer away."""
        from app.api import auth as auth_module

        calls = []
        real_verify = auth_module.verify_password
        monkeypatch.setattr(
            auth_module,
            "verify_password",
            lambda password, hashed: calls.append(hashed) or real_verify(password, hashed),
        )

        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "no-such-user@example.com", "password": PASSWORD}
        )
        assert response.status_code == 401
        assert len(calls) == 1, "a login for an unknown address skipped the password check"
        assert calls[0].startswith("$2b$"), "it should be checked against a real bcrypt hash"

    def test_the_message_is_identical_either_way(self, unauthenticated_client):
        unauthenticated_client.post(
            "/api/auth/register", json={"email": "real@example.com", "password": PASSWORD}
        )
        unknown = unauthenticated_client.post(
            "/api/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
        )
        wrong_password = unauthenticated_client.post(
            "/api/auth/login", json={"email": "real@example.com", "password": "not-the-password"}
        )
        assert unknown.status_code == wrong_password.status_code == 401
        assert unknown.json()["detail"] == wrong_password.json()["detail"]
