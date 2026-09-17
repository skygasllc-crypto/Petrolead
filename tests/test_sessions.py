"""Ending sessions: password change, "sign out other devices", and an admin
revoking a compromised account's tokens.

Session tokens are stateless and last a week, so without these a stolen
token simply works until it expires. Each account carries a version counter
that every token is stamped with; bumping it is what ends the sessions.
"""

from __future__ import annotations

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "an-entirely-different-one"
ADMIN_EMAIL = "admin@example.com"


def _register(client, email, password=PASSWORD):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestRevokingYourOwnSessions:
    def test_other_sessions_stop_working_and_this_one_continues(self, unauthenticated_client):
        api = unauthenticated_client
        _, first = _register(api, "user@example.com")
        # A second sign-in, as if from another device.
        second = _auth(
            api.post(
                "/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}
            ).json()["access_token"]
        )
        assert api.get("/api/auth/me", headers=second).status_code == 200

        revoked = api.post("/api/auth/revoke-sessions", headers=second)
        assert revoked.status_code == 200
        kept = _auth(revoked.json()["access_token"])

        # The device that asked keeps working; the other one is finished.
        assert api.get("/api/auth/me", headers=kept).status_code == 200
        assert api.get("/api/auth/me", headers=first).status_code == 401
        assert api.get("/api/auth/me", headers=second).status_code == 401

    def test_the_message_says_the_session_ended(self, unauthenticated_client):
        api = unauthenticated_client
        _, headers = _register(api, "user@example.com")
        api.post("/api/auth/revoke-sessions", headers=headers)
        response = api.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert "session has ended" in response.json()["detail"].lower()


class TestChangingPassword:
    def test_it_needs_the_current_password(self, unauthenticated_client):
        api = unauthenticated_client
        _, headers = _register(api, "user@example.com")
        response = api.post(
            "/api/auth/change-password",
            json={"current_password": "not-the-password", "new_password": NEW_PASSWORD},
            headers=headers,
        )
        assert response.status_code == 401
        # A borrowed token alone must not be enough to take the account over.
        assert api.post(
            "/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}
        ).status_code == 200

    def test_changing_it_ends_every_other_session(self, unauthenticated_client):
        api = unauthenticated_client
        _, stolen = _register(api, "user@example.com")
        owner = _auth(
            api.post(
                "/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}
            ).json()["access_token"]
        )

        changed = api.post(
            "/api/auth/change-password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=owner,
        )
        assert changed.status_code == 200

        assert api.get("/api/auth/me", headers=stolen).status_code == 401
        kept = _auth(changed.json()["access_token"])
        assert api.get("/api/auth/me", headers=kept).status_code == 200

    def test_the_new_password_works_and_the_old_one_does_not(self, unauthenticated_client):
        api = unauthenticated_client
        _, headers = _register(api, "user@example.com")
        api.post(
            "/api/auth/change-password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=headers,
        )
        assert api.post(
            "/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}
        ).status_code == 401
        assert api.post(
            "/api/auth/login", json={"email": "user@example.com", "password": NEW_PASSWORD}
        ).status_code == 200

    def test_a_weak_new_password_is_refused(self, unauthenticated_client):
        api = unauthenticated_client
        _, headers = _register(api, "user@example.com")
        response = api.post(
            "/api/auth/change-password",
            json={"current_password": PASSWORD, "new_password": "short"},
            headers=headers,
        )
        assert response.status_code == 422


class TestAdminRevokingSessions:
    def test_an_admin_can_end_a_users_sessions_without_blocking_them(
        self, unauthenticated_client, monkeypatch
    ):
        from app.api import auth as auth_module
        from app.config import get_settings as real_get_settings

        settings = real_get_settings().model_copy(update={"admin_emails": ADMIN_EMAIL})
        monkeypatch.setattr(auth_module, "get_settings", lambda: settings)

        api = unauthenticated_client
        _, admin = _register(api, ADMIN_EMAIL)
        user_id, user = _register(api, "user@example.com")

        response = api.post(f"/api/admin/users/{user_id}/revoke-sessions", headers=admin)
        assert response.status_code == 200, response.text

        assert api.get("/api/auth/me", headers=user).status_code == 401
        # Not blocked — they can simply log in again.
        assert api.post(
            "/api/auth/login", json={"email": "user@example.com", "password": PASSWORD}
        ).status_code == 200
        # And the admin's own session is untouched.
        assert api.get("/api/auth/me", headers=admin).status_code == 200

    def test_a_normal_user_cannot_revoke_anyone(self, unauthenticated_client):
        api = unauthenticated_client
        victim_id, _ = _register(api, "victim@example.com")
        _, attacker = _register(api, "attacker@example.com")
        response = api.post(f"/api/admin/users/{victim_id}/revoke-sessions", headers=attacker)
        assert response.status_code == 403
