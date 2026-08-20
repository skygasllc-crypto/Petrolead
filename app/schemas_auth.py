"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MIN_PASSWORD_LENGTH = 8


class RegisterRequestSchema(BaseModel):
    """Body for POST /api/auth/register."""

    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)

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


class UpdateUserStatusRequestSchema(BaseModel):
    """Body for PATCH /api/admin/users/{user_id} — block/unblock a user."""

    is_active: bool
