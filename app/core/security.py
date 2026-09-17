"""Password hashing and JWT session tokens for user accounts.

Passwords are hashed with bcrypt (via the `bcrypt` package directly —
salted, adaptive, industry standard) and never stored or logged in plain
text. Sessions are stateless signed JWTs (HS256, `SECRET_KEY` from
config) carried as a Bearer token; there's no server-side session store
to manage, at the cost of not being able to revoke a token before it
expires (`ACCESS_TOKEN_EXPIRE_MINUTES`, default one week).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import bcrypt
import jwt

from app.config import Settings
from app.database.models import utcnow

JWT_ALGORITHM = "HS256"


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
