"""Pydantic schemas for plans, credits and admin billing controls."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    # End of the paid period; None for plans an admin assigned (no end date).
    paid_until: datetime | None
    expired: bool
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


class PaymentMethodSchema(BaseModel):
    currency: str
    symbol: str
    name: str
    network: str
    address: str


class CreateOrderRequestSchema(BaseModel):
    """Body for POST /api/billing/orders."""

    plan: str = Field(min_length=1, max_length=50)
    credits_per_month: int = Field(gt=0)
    billing_period: Literal["monthly", "yearly"]
    currency: Literal["BTC", "USDT_TRC20", "TRX"]


class MarkOrderPaidRequestSchema(BaseModel):
    """Body for POST /api/billing/orders/{order_id}/paid — the customer's
    "I have paid". The transaction ID is optional; orders are identified by
    their own reference code."""

    tx_hash: str | None = Field(default=None, max_length=100)


class ConfirmPaymentRequestSchema(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    # Optionally record the transaction the admin found while checking.
    tx_hash: str | None = Field(default=None, max_length=100)


class RejectPaymentRequestSchema(BaseModel):
    """A rejection always tells the customer why."""

    note: str = Field(min_length=1, max_length=500)

    @field_validator("note")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Add a note telling the customer why.")
        return value


class PaymentOrderSchema(BaseModel):
    id: str
    reference: str
    plan: str
    plan_name: str
    credits_per_month: int
    billing_period: str
    amount_usd: str
    currency: str
    coin_symbol: str
    coin_name: str
    network: str
    pay_address: str
    amount_crypto: str
    usd_rate: str | None
    status: str
    tx_hash: str | None
    explorer_url: str | None
    admin_note: str | None
    created_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None


class AdminPaymentOrderSchema(PaymentOrderSchema):
    customer_email: str
    paid_after_quote_expired: bool


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
