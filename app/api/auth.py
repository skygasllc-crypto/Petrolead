"""Account creation, login, and "who am I" endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database.connection import get_db
from app.database.models import User
from app.schemas_auth import (
    LoginRequestSchema,
    RegisterRequestSchema,
    TokenResponseSchema,
    UserSchema,
)

logger = logging.getLogger("petrolead.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


def _sync_admin_status(user: User, settings) -> None:
    """Grants admin access when the account's email is in `ADMIN_EMAILS`.
    Only ever grants, never revokes — removing an email from the setting
    doesn't silently demote an existing admin; that's an explicit action
    another admin takes via `PATCH /admin/users/{id}`."""
    if not user.is_admin and user.email in settings.admin_emails_list:
        user.is_admin = True


@router.post("/register", response_model=TokenResponseSchema)
def register(payload: RegisterRequestSchema, db: Session = Depends(get_db)) -> TokenResponseSchema:
    email = payload.email.lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    settings = get_settings()
    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_admin=email in settings.admin_emails_list,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New account registered: %s", user.id)

    token = create_access_token(user.id, settings=settings)
    return TokenResponseSchema(access_token=token, user=user)


@router.post("/login", response_model=TokenResponseSchema)
def login(payload: LoginRequestSchema, db: Session = Depends(get_db)) -> TokenResponseSchema:
    email = payload.email.lower()
    invalid_credentials = HTTPException(
        status_code=401, detail="Incorrect email or password."
    )

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials
    if not user.is_active:
        raise invalid_credentials

    settings = get_settings()
    _sync_admin_status(user, settings)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, settings=settings)
    return TokenResponseSchema(access_token=token, user=user)


@router.get("/me", response_model=UserSchema)
def get_me(current_user: User = Depends(get_current_user)) -> UserSchema:
    return current_user
