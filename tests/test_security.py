from datetime import timedelta

from app.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

TEST_SETTINGS = Settings(secret_key="test-secret-key-do-not-use-in-prod")


class TestPasswordHashing:
    def test_hash_is_not_the_plaintext_password(self):
        hashed = hash_password("correct-horse-battery")
        assert hashed != "correct-horse-battery"

    def test_correct_password_verifies(self):
        hashed = hash_password("correct-horse-battery")
        assert verify_password("correct-horse-battery", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("correct-horse-battery")
        assert verify_password("wrong-password", hashed) is False

    def test_same_password_hashes_differently_each_time(self):
        # bcrypt salts each hash — this is what makes rainbow-table attacks
        # against a leaked database ineffective.
        assert hash_password("correct-horse-battery") != hash_password("correct-horse-battery")

    def test_malformed_hash_never_verifies(self):
        assert verify_password("anything", "not-a-real-bcrypt-hash") is False


class TestAccessTokens:
    def test_token_round_trips_to_the_same_user_id(self):
        token = create_access_token("user-123", token_version=0, settings=TEST_SETTINGS)
        claims = decode_access_token(token, settings=TEST_SETTINGS)
        assert claims.user_id == "user-123"
        assert claims.token_version == 0

    def test_the_version_it_was_issued_at_is_carried_in_the_token(self):
        token = create_access_token("user-123", token_version=7, settings=TEST_SETTINGS)
        assert decode_access_token(token, settings=TEST_SETTINGS).token_version == 7

    def test_garbage_token_decodes_to_none(self):
        assert decode_access_token("not-a-real-token", settings=TEST_SETTINGS) is None

    def test_token_signed_with_a_different_secret_is_rejected(self):
        other_settings = Settings(secret_key="a-completely-different-secret")
        token = create_access_token("user-123", token_version=0, settings=TEST_SETTINGS)
        assert decode_access_token(token, settings=other_settings) is None

    def test_a_token_without_a_version_is_refused(self):
        """Tokens minted before session revocation existed. Treating them as
        version 0 would leave them unrevokable, so they fail closed."""
        import jwt

        from app.core.security import JWT_ALGORITHM
        from app.database.models import utcnow

        legacy = jwt.encode(
            {"sub": "user-123", "exp": utcnow() + timedelta(minutes=60)},
            TEST_SETTINGS.secret_key,
            algorithm=JWT_ALGORITHM,
        )
        assert decode_access_token(legacy, settings=TEST_SETTINGS) is None
