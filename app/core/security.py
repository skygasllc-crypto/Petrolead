"""Password hashing and JWT session tokens for user accounts.

Passwords are hashed with bcrypt (via the `bcrypt` package directly —
salted, adaptive, industry standard) and never stored or logged in plain
text. Sessions are stateless signed JWTs (HS256, `SECRET_KEY` from
config) carried as a Bearer token; there's no server-side session store
to manage, at the cost of not being able to revoke a token before it
expires (`ACCESS_TOKEN_EXPIRE_MINUTES`, default one week).
"""

from __future__ import annotations

from datetime import timedelta

import bcrypt
import jwt

from app.config import Settings
from app.database.models import utcnow

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for rows we created) — never a match.
        return False


def create_access_token(user_id: str, *, settings: Settings) -> str:
    expires_at = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, settings: Settings) -> str | None:
    """Return the user id encoded in a valid, unexpired token, else None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
