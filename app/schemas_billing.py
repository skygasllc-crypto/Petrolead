"""Pydantic schemas for plans, credits and admin billing controls."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubscriptionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: str
    credits_per_month: int
    credits_balance: int
    renews_at: datetime


class BillingSummarySchema(BaseModel):
    """GET /api/billing/me — the signed-in user's plan, credits and usage."""

    exempt: bool
    plan: str | None
    plan_name: str | None
    credits_balance: int
    credits_per_month: int | None
    renews_at: datetime | None
    discovery_searches_today: int
    discovery_searches_per_day: int | None
    max_results_per_search: int | None
    bulk_lookup: bool
    export: bool
    # How many scheduled searches the plan allows; None means unlimited.
    scheduled_searches: int | None


class AssignPlanRequestSchema(BaseModel):
    """Body for PUT /api/admin/users/{user_id}/subscription."""

    plan: str = Field(min_length=1, max_length=50)
    credits_per_month: int = Field(gt=0)


class AdjustCreditsRequestSchema(BaseModel):
    """Body for POST /api/admin/users/{user_id}/credits."""

    amount: int = Field(ge=-1_000_000, le=1_000_000)
    note: str | None = Field(default=None, max_length=300)

    @field_validator("amount")
    @classmethod
    def _not_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must not be zero")
        return value
