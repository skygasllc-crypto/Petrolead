"""Recovering a lost password: an emailed one-time link, or one an admin
hands over when the app can't send email."""

from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from app.core.security import JWT_ALGORITHM

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "an-entirely-different-one"
ADMIN_EMAIL = "admin@example.com"


def _register(client, email, password=PASSWORD):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _token_from(url):
    return parse_qs(urlparse(url).query)["token"][0]


@pytest.fixture()
def sent(monkeypatch):
    """Captures reset emails instead of sending them."""
    from app.services import notifications

    outbox = []
    monkeypatch.setattr(
        notifications,
        "send_password_reset",
        lambda email, url, minutes: outbox.append({"email": email, "url": url}),
    )
    return outbox


def _request_reset(client, sent, email):
    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 202, response.text
    return _token_from(sent[-1]["url"])


class TestForgotPassword:
    def test_sends_a_link_to_an_existing_account(self, unauthenticated_client, sent):
        _register(unauthenticated_client, "user@example.com")
        response = unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "User@Example.com"}
        )
        assert response.status_code == 202
        assert len(sent) == 1
        assert sent[0]["email"] == "user@example.com"
        assert "/reset-password?token=" in sent[0]["url"]

    def test_unknown_address_gets_the_same_answer_and_no_email(
        self, unauthenticated_client, sent
    ):
        _register(unauthenticated_client, "user@example.com")
        known = unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "user@example.com"}
        )
        unknown = unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        assert unknown.status_code == known.status_code == 202
        assert unknown.json() == known.json()
        assert [m["email"] for m in sent] == ["user@example.com"]

    def test_without_smtp_nothing_is_sent_and_the_link_is_not_logged(
        self, unauthenticated_client
    ):
        # caplog can't see app loggers (propagation is off), so capture from
        # the loggers themselves — see tests/test_contact_providers.py.
        from app.api import auth
        from app.services import notifications

        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture(level=logging.DEBUG)
        loggers = [auth.logger, notifications.logger]
        for logger in loggers:
            logger.addHandler(handler)
        try:
            _register(unauthenticated_client, "user@example.com")
            response = unauthenticated_client.post(
                "/api/auth/forgot-password", json={"email": "user@example.com"}
            )
        finally:
            for logger in loggers:
                logger.removeHandler(handler)

        assert response.status_code == 202
        messages = [r.getMessage() for r in records]
        assert any("email isn't configured" in m for m in messages)
        assert not any("token=" in m for m in messages)


class TestResetPassword:
    def test_link_sets_a_new_password_and_signs_in(self, unauthenticated_client, sent):
        api = unauthenticated_client
        _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")

        response = api.post(
            "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
        assert response.status_code == 200, response.text
        session = {"Authorization": f"Bearer {response.json()['access_token']}"}
        assert api.get("/api/auth/me", headers=session).status_code == 200

        assert _login(api, "user@example.com", PASSWORD).status_code == 401
        assert _login(api, "user@example.com", NEW_PASSWORD).status_code == 200

    def test_existing_sessions_end(self, unauthenticated_client, sent):
        api = unauthenticated_client
        _, old_session = _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")
        api.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
        assert api.get("/api/auth/me", headers=old_session).status_code == 401

    def test_a_link_works_only_once(self, unauthenticated_client, sent):
        api = unauthenticated_client
        _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")
        first = api.post(
            "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
        second = api.post(
            "/api/auth/reset-password", json={"token": token, "new_password": "yet-another-one"}
        )
        assert first.status_code == 200
        assert second.status_code == 400

    def test_a_link_dies_when_the_password_changes_another_way(
        self, unauthenticated_client, sent
    ):
        api = unauthenticated_client
        _, session = _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")
        api.post(
            "/api/auth/change-password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=session,
        )
        response = api.post(
            "/api/auth/reset-password", json={"token": token, "new_password": "yet-another-one"}
        )
        assert response.status_code == 400

    def test_an_expired_link_is_refused(self, unauthenticated_client, sent):
        from app.config import get_settings
        from app.database.models import utcnow

        api = unauthenticated_client
        _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")
        settings = get_settings()
        claims = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        claims["exp"] = utcnow() - timedelta(minutes=1)
        expired = jwt.encode(claims, settings.secret_key, algorithm=JWT_ALGORITHM)

        response = api.post(
            "/api/auth/reset-password", json={"token": expired, "new_password": NEW_PASSWORD}
        )
        assert response.status_code == 400

    def test_a_session_token_is_not_a_reset_link(self, unauthenticated_client):
        api = unauthenticated_client
        _, session = _register(api, "user@example.com")
        session_token = session["Authorization"].removeprefix("Bearer ")
        response = api.post(
            "/api/auth/reset-password",
            json={"token": session_token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 400

    def test_a_reset_link_is_not_a_session_token(self, unauthenticated_client, sent):
        api = unauthenticated_client
        _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")
        response = api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_a_short_new_password_is_rejected(self, unauthenticated_client, sent):
        api = unauthenticated_client
        _register(api, "user@example.com")
        token = _request_reset(api, sent, "user@example.com")
        response = api.post(
            "/api/auth/reset-password", json={"token": token, "new_password": "short"}
        )
        assert response.status_code == 422


class TestAdminResetLink:
    def test_an_admin_can_issue_a_working_link(self, unauthenticated_client, monkeypatch):
        from app.api import auth as auth_module
        from app.config import get_settings as real_get_settings

        settings = real_get_settings().model_copy(update={"admin_emails": ADMIN_EMAIL})
        monkeypatch.setattr(auth_module, "get_settings", lambda: settings)

        api = unauthenticated_client
        _, admin = _register(api, ADMIN_EMAIL)
        user_id, _ = _register(api, "user@example.com")

        response = api.post(f"/api/admin/users/{user_id}/password-reset-link", headers=admin)
        assert response.status_code == 200, response.text
        token = _token_from(response.json()["reset_url"])

        # Issuing it changes nothing on its own.
        assert _login(api, "user@example.com", PASSWORD).status_code == 200

        reset = api.post(
            "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
        assert reset.status_code == 200
        assert _login(api, "user@example.com", NEW_PASSWORD).status_code == 200

    def test_a_normal_user_cannot_issue_links(self, unauthenticated_client):
        api = unauthenticated_client
        victim_id, _ = _register(api, "victim@example.com")
        _, attacker = _register(api, "attacker@example.com")
        response = api.post(f"/api/admin/users/{victim_id}/password-reset-link", headers=attacker)
        assert response.status_code == 403
