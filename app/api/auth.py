"""Account creation, login, password recovery, and "who am I" endpoints."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.security import (
    PASSWORD_RESET_EXPIRE_MINUTES,
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    password_reset_token_matches,
    verify_password,
)
from app.database.connection import get_db
from app.database.models import User
from app.schemas_auth import (
    ChangePasswordRequestSchema,
    ForgotPasswordRequestSchema,
    LoginRequestSchema,
    RegisterRequestSchema,
    ResetPasswordRequestSchema,
    TokenResponseSchema,
    UserSchema,
)
from app.services import notifications

logger = logging.getLogger("petrolead.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@lru_cache(maxsize=1)
def _timing_equaliser_hash() -> str:
    """A throwaway hash to check failed logins against, so a login for an
    address with no account costs the same as one for an address with an
    account. Computed once, on first use."""
    return hash_password("no-account-with-this-address")


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

    token = create_access_token(user.id, token_version=user.token_version, settings=settings)
    return TokenResponseSchema(access_token=token, user=user)


@router.post("/login", response_model=TokenResponseSchema)
def login(payload: LoginRequestSchema, db: Session = Depends(get_db)) -> TokenResponseSchema:
    email = payload.email.lower()
    invalid_credentials = HTTPException(
        status_code=401, detail="Incorrect email or password."
    )

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        # Hash anyway. Skipping it would return "no such account" in a
        # fraction of the time a real password check takes, which is enough
        # to let someone work out which addresses have accounts here.
        verify_password(payload.password, _timing_equaliser_hash())
        raise invalid_credentials
    if not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials
    if not user.is_active:
        raise invalid_credentials

    settings = get_settings()
    _sync_admin_status(user, settings)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, token_version=user.token_version, settings=settings)
    return TokenResponseSchema(access_token=token, user=user)


@router.get("/me", response_model=UserSchema)
def get_me(current_user: User = Depends(get_current_user)) -> UserSchema:
    return current_user


def _reissue_after_revoking(db: Session, user: User) -> TokenResponseSchema:
    """End every existing session for `user` and hand back a token for this
    one, so whoever asked isn't logged out of the page they're standing on."""
    user.token_version += 1
    db.commit()
    db.refresh(user)
    token = create_access_token(
        user.id, token_version=user.token_version, settings=get_settings()
    )
    return TokenResponseSchema(access_token=token, user=user)


@router.post("/change-password", response_model=TokenResponseSchema)
def change_password(
    payload: ChangePasswordRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponseSchema:
    """Change the password, and end every other session in the process — a
    password change that left a stolen token working wouldn't be much of a
    remedy. The current password is required, so a borrowed token alone
    can't be used to take the account over."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Your current password isn't right.")

    current_user.hashed_password = hash_password(payload.new_password)
    logger.info("Password changed for user %s", current_user.id)
    return _reissue_after_revoking(db, current_user)


@router.post("/revoke-sessions", response_model=TokenResponseSchema)
def revoke_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponseSchema:
    """Sign out everywhere else. Every token issued before now stops working
    on its next request; this session continues with the token returned."""
    logger.info("User %s revoked their other sessions", current_user.id)
    return _reissue_after_revoking(db, current_user)


def password_reset_url(user: User, settings) -> str:
    """A one-time link to the reset page, valid for an hour."""
    token = create_password_reset_token(
        user.id, hashed_password=user.hashed_password, settings=settings
    )
    return f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"


@router.post("/forgot-password", status_code=202)
def forgot_password(
    payload: ForgotPasswordRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Email a reset link if the address has an active account. The answer
    is the same either way, so this can't be used to find out who has an
    account here."""
    user = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()
    if user is not None and user.is_active:
        logger.info("Password reset requested for user %s", user.id)
        background_tasks.add_task(
            notifications.send_password_reset,
            user.email,
            password_reset_url(user, get_settings()),
            PASSWORD_RESET_EXPIRE_MINUTES,
        )
    return {
        "detail": "If an account exists for that email, a link to reset its password is on "
        "its way."
    }


@router.post("/reset-password", response_model=TokenResponseSchema)
def reset_password(
    payload: ResetPasswordRequestSchema, db: Session = Depends(get_db)
) -> TokenResponseSchema:
    """Set a new password from an emailed link, end every existing session,
    and sign in. The link stops working once used, because it is tied to the
    password it was issued against."""
    invalid_link = HTTPException(
        status_code=400,
        detail="This reset link is invalid or has expired. Ask for a new one.",
    )
    settings = get_settings()
    claims = decode_password_reset_token(payload.token, settings=settings)
    if claims is None:
        raise invalid_link
    user_id, fingerprint = claims
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise invalid_link
    if not password_reset_token_matches(fingerprint, user.hashed_password, settings):
        raise invalid_link

    user.hashed_password = hash_password(payload.new_password)
    _sync_admin_status(user, settings)
    logger.info("Password reset for user %s", user.id)
    return _reissue_after_revoking(db, user)
