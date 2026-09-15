"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas_billing import SubscriptionSchema

MIN_PASSWORD_LENGTH = 8
# bcrypt's hard cap is 72 *bytes* — passing more raises ValueError (as of
# bcrypt 4+) instead of the old silent-truncation behavior. Enforced here as
# a clean 422 at registration, rather than letting app.core.security.
# hash_password crash with an unhandled 500 for a password the schema's
# max_length=128 (in characters) would otherwise still let through.
MAX_PASSWORD_BYTES = 72


class RegisterRequestSchema(BaseModel):
    """Body for POST /api/auth/register."""

    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)

    @field_validator("password")
    @classmethod
    def _password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long.")
        return value

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class LoginRequestSchema(BaseModel):
    """Body for POST /api/auth/login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    is_admin: bool
    created_at: datetime


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSchema


class AdminUserSchema(BaseModel):
    """A user row as shown to an admin — includes `is_active` (unlike the
    plain `UserSchema` a user sees about themselves)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime
    subscription: SubscriptionSchema | None = None


class UpdateUserStatusRequestSchema(BaseModel):
    """Body for PATCH /api/admin/users/{user_id} — block/unblock a user."""

    is_active: bool
