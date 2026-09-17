"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.database.models import User

# auto_error=False so a missing/malformed header raises our own 401 with a
# clear message, instead of FastAPI's generic "Not authenticated".
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Not authenticated. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    claims = decode_access_token(credentials.credentials, settings=get_settings())
    if claims is None:
        raise unauthorized

    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise unauthorized

    # The account's sessions were revoked (password change, "sign out other
    # devices", or an admin ending them) after this token was issued.
    if claims.token_version != user.token_version:
        raise HTTPException(
            status_code=401,
            detail="This session has ended. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user
