"""Password hashing and JWT session tokens for user accounts.

Passwords are hashed with bcrypt (via the `bcrypt` package directly —
salted, adaptive, industry standard) and never stored or logged in plain
text. Sessions are stateless signed JWTs (HS256, `SECRET_KEY` from
config) carried as a Bearer token; there's no server-side session store
to manage, at the cost of not being able to revoke a token before it
expires (`ACCESS_TOKEN_EXPIRE_MINUTES`, default one week).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import timedelta

import bcrypt
import jwt

from app.config import Settings
from app.database.models import utcnow

JWT_ALGORITHM = "HS256"

PASSWORD_RESET_PURPOSE = "password_reset"
PASSWORD_RESET_EXPIRE_MINUTES = 60


@dataclass(frozen=True)
class TokenClaims:
    """What a valid token says: who it belongs to, and which generation of
    that account's sessions it came from."""

    user_id: str
    token_version: int


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for rows we created) — never a match.
        return False


def create_access_token(user_id: str, *, token_version: int, settings: Settings) -> str:
    expires_at = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "ver": token_version, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, settings: Settings) -> TokenClaims | None:
    """The claims of a valid, unexpired token, else None.

    A token without a version claim predates session revocation, so it is
    refused rather than assumed to be generation zero: failing closed costs
    one sign-in, and the alternative would leave old tokens unrevokable.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

    user_id = payload.get("sub")
    version = payload.get("ver")
    if not isinstance(user_id, str) or not isinstance(version, int) or isinstance(version, bool):
        return None
    return TokenClaims(user_id=user_id, token_version=version)


def _password_fingerprint(hashed_password: str, settings: Settings) -> str:
    """A short keyed digest of the stored hash. Stamped into a reset token
    so the token dies the moment the password changes — which makes it
    single-use without a table of issued tokens. Keyed, so the token
    reveals nothing about the hash itself."""
    digest = hmac.new(
        settings.secret_key.encode("utf-8"), hashed_password.encode("utf-8"), hashlib.sha256
    )
    return digest.hexdigest()[:32]


def create_password_reset_token(user_id: str, *, hashed_password: str, settings: Settings) -> str:
    """A signed link token that lets its holder set a new password once,
    within the hour. It carries no session version, so it can never be
    used as a session token (see `decode_access_token`)."""
    expires_at = utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "purpose": PASSWORD_RESET_PURPOSE,
        "pwd": _password_fingerprint(hashed_password, settings),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_password_reset_token(token: str, *, settings: Settings) -> tuple[str, str] | None:
    """`(user_id, password_fingerprint)` for a valid, unexpired reset token,
    else None. The caller still has to compare the fingerprint against the
    account's current hash — see `password_reset_token_matches`."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != PASSWORD_RESET_PURPOSE:
        return None
    user_id = payload.get("sub")
    fingerprint = payload.get("pwd")
    if not isinstance(user_id, str) or not isinstance(fingerprint, str):
        return None
    return user_id, fingerprint


def password_reset_token_matches(
    fingerprint: str, hashed_password: str, settings: Settings
) -> bool:
    return hmac.compare_digest(fingerprint, _password_fingerprint(hashed_password, settings))
