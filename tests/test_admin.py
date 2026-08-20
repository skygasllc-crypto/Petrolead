"""Tests for admin user management: GET/PATCH /api/admin/users.

Admin status is normally granted by matching `ADMIN_EMAILS` at
register/login time (see `app.api.auth._sync_admin_status`) — these tests
monkeypatch `app.api.auth.get_settings` with a copy of the real cached
settings that just has `admin_emails` overridden, so JWT signing/decoding
(secret key, expiry, etc.) stays consistent with the rest of the app.
"""

from app.api import auth as auth_module
from app.config import get_settings as real_get_settings

PASSWORD = "correct-horse-battery"


def _settings_with_admin(email: str):
    return real_get_settings().model_copy(update={"admin_emails": email})


def _register(client, email, password=PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _patch_admin_emails(monkeypatch, email: str) -> None:
    monkeypatch.setattr(auth_module, "get_settings", lambda: _settings_with_admin(email))


def _make_admin_client(unauthenticated_client, monkeypatch, email="admin@example.com"):
    _patch_admin_emails(monkeypatch, email)
    response = _register(unauthenticated_client, email)
    assert response.json()["user"]["is_admin"] is True
    token = response.json()["access_token"]
    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"
    return unauthenticated_client


class TestAdminBootstrapping:
    def test_matching_admin_email_becomes_admin_on_register(
        self, unauthenticated_client, monkeypatch
    ):
        _patch_admin_emails(monkeypatch, "admin@example.com")
        response = _register(unauthenticated_client, "admin@example.com")
        assert response.json()["user"]["is_admin"] is True

    def test_non_matching_email_is_not_admin(self, unauthenticated_client, monkeypatch):
        _patch_admin_emails(monkeypatch, "admin@example.com")
        response = _register(unauthenticated_client, "someone-else@example.com")
        assert response.json()["user"]["is_admin"] is False

    def test_default_admin_emails_empty_grants_no_one_admin(self, unauthenticated_client):
        response = _register(unauthenticated_client, "nobody-special@example.com")
        assert response.json()["user"]["is_admin"] is False

    def test_admin_status_granted_on_login_if_added_later(
        self, unauthenticated_client, monkeypatch
    ):
        response = _register(unauthenticated_client, "later-admin@example.com")
        assert response.json()["user"]["is_admin"] is False

        _patch_admin_emails(monkeypatch, "later-admin@example.com")
        login = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "later-admin@example.com", "password": PASSWORD},
        )
        assert login.json()["user"]["is_admin"] is True


class TestAdminEndpointsRequireAdmin:
    def test_non_admin_gets_403(self, client):
        response = client.get("/api/admin/users")
        assert response.status_code == 403

    def test_unauthenticated_gets_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/admin/users")
        assert response.status_code == 401


class TestAdminUserManagement:
    def test_list_users_includes_everyone(self, unauthenticated_client, monkeypatch):
        admin_client = _make_admin_client(unauthenticated_client, monkeypatch)
        _register(admin_client, "regular@example.com")

        response = admin_client.get("/api/admin/users")
        assert response.status_code == 200
        emails = {u["email"] for u in response.json()}
        assert {"admin@example.com", "regular@example.com"} <= emails

    def test_block_a_user_prevents_future_login(self, unauthenticated_client, monkeypatch):
        admin_client = _make_admin_client(unauthenticated_client, monkeypatch)
        target = _register(admin_client, "blockme@example.com").json()["user"]

        response = admin_client.patch(f"/api/admin/users/{target['id']}", json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        login = admin_client.post(
            "/api/auth/login", json={"email": "blockme@example.com", "password": PASSWORD}
        )
        assert login.status_code == 401

    def test_blocking_invalidates_an_existing_token_immediately(
        self, unauthenticated_client, monkeypatch
    ):
        admin_client = _make_admin_client(unauthenticated_client, monkeypatch)
        target_response = _register(admin_client, "blockme2@example.com")
        target = target_response.json()["user"]
        target_token = target_response.json()["access_token"]

        admin_client.patch(f"/api/admin/users/{target['id']}", json={"is_active": False})

        original_header = admin_client.headers["Authorization"]
        admin_client.headers["Authorization"] = f"Bearer {target_token}"
        me_response = admin_client.get("/api/auth/me")
        admin_client.headers["Authorization"] = original_header

        assert me_response.status_code == 401

    def test_admin_cannot_block_their_own_account(self, unauthenticated_client, monkeypatch):
        admin_client = _make_admin_client(unauthenticated_client, monkeypatch)
        me = admin_client.get("/api/auth/me").json()

        response = admin_client.patch(f"/api/admin/users/{me['id']}", json={"is_active": False})
        assert response.status_code == 400

    def test_unblock_a_user_restores_login(self, unauthenticated_client, monkeypatch):
        admin_client = _make_admin_client(unauthenticated_client, monkeypatch)
        target = _register(admin_client, "reblockme@example.com").json()["user"]

        admin_client.patch(f"/api/admin/users/{target['id']}", json={"is_active": False})
        response = admin_client.patch(f"/api/admin/users/{target['id']}", json={"is_active": True})
        assert response.status_code == 200
        assert response.json()["is_active"] is True

        login = admin_client.post(
            "/api/auth/login", json={"email": "reblockme@example.com", "password": PASSWORD}
        )
        assert login.status_code == 200

    def test_block_nonexistent_user_returns_404(self, unauthenticated_client, monkeypatch):
        admin_client = _make_admin_client(unauthenticated_client, monkeypatch)
        response = admin_client.patch("/api/admin/users/does-not-exist", json={"is_active": False})
        assert response.status_code == 404
