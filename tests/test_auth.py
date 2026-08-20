class TestRegister:
    def test_register_creates_account_and_returns_token(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "new-trader@example.com", "password": "correct-horse-battery"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["email"] == "new-trader@example.com"
        assert "hashed_password" not in body["user"]

    def test_email_is_lowercased(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "Mixed.Case@Example.COM", "password": "correct-horse-battery"},
        )
        assert response.json()["user"]["email"] == "mixed.case@example.com"

    def test_duplicate_email_rejected(self, unauthenticated_client):
        payload = {"email": "dup@example.com", "password": "correct-horse-battery"}
        first = unauthenticated_client.post("/api/auth/register", json=payload)
        second = unauthenticated_client.post("/api/auth/register", json=payload)
        assert first.status_code == 200
        assert second.status_code == 409

    def test_invalid_email_rejected(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "correct-horse-battery"},
        )
        assert response.status_code == 422

    def test_short_password_rejected(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/register", json={"email": "a@example.com", "password": "short"}
        )
        assert response.status_code == 422

    def test_password_is_never_returned_in_plaintext_or_hashed(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "check@example.com", "password": "correct-horse-battery"},
        )
        assert "password" not in str(response.json())


class TestLogin:
    def _register(self, client, email="trader@example.com", password="correct-horse-battery"):
        return client.post("/api/auth/register", json={"email": email, "password": password})

    def test_login_with_correct_credentials(self, unauthenticated_client):
        self._register(unauthenticated_client)
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "trader@example.com", "password": "correct-horse-battery"},
        )
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_login_with_wrong_password(self, unauthenticated_client):
        self._register(unauthenticated_client)
        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "trader@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 401

    def test_login_with_unknown_email(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "correct-horse-battery"},
        )
        assert response.status_code == 401

    def test_login_error_does_not_reveal_which_field_was_wrong(self, unauthenticated_client):
        self._register(unauthenticated_client)
        wrong_password = unauthenticated_client.post(
            "/api/auth/login", json={"email": "trader@example.com", "password": "wrong-password"}
        )
        unknown_email = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "correct-horse-battery"},
        )
        assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


class TestMe:
    def test_me_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_returns_current_user(self, unauthenticated_client):
        register = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "whoami@example.com", "password": "correct-horse-battery"},
        )
        token = register.json()["access_token"]
        response = unauthenticated_client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["email"] == "whoami@example.com"


class TestProtectedEndpoints:
    def test_companies_requires_auth(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/companies").status_code == 401

    def test_discover_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.post("/api/discover", json={"limit": 10})
        assert response.status_code == 401

    def test_emails_requires_auth(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/emails").status_code == 401

    def test_saved_searches_requires_auth(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/saved-searches").status_code == 401

    def test_garbage_token_rejected(self, unauthenticated_client):
        response = unauthenticated_client.get(
            "/api/companies", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401

    def test_health_check_does_not_require_auth(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/health").status_code == 200

    def test_valid_token_grants_access(self, unauthenticated_client):
        register = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "access@example.com", "password": "correct-horse-battery"},
        )
        token = register.json()["access_token"]
        response = unauthenticated_client.get(
            "/api/companies", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
