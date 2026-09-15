"""Plan catalogue: prices, credit tiers and usage limits for each paid plan.

Mirrors the public pricing page (`frontend/src/components/marketing/pricing.js`)
— keep the two in sync when prices or limits change. Payments are always
priced from here, never from anything the browser sends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# Yearly billing takes 25% off the monthly price, rounded to the dollar.
YEARLY_DISCOUNT = Decimal("0.25")

BILLING_PERIOD_MONTHS = {"monthly": 1, "yearly": 12}


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    # Monthly email-credit tier -> monthly price in whole US dollars.
    monthly_prices: dict[int, int] = field(repr=False)
    discovery_searches_per_day: int
    max_results_per_search: int
    bulk_lookup: bool
    export: bool
    # How many scheduled searches an account may keep; None means unlimited.
    scheduled_searches: int | None

    @property
    def credit_tiers(self) -> tuple[int, ...]:
        return tuple(self.monthly_prices)


PLANS: dict[str, Plan] = {
    "basic": Plan(
        id="basic",
        name="Basic",
        monthly_prices={1000: 20},
        discovery_searches_per_day=5,
        max_results_per_search=10,
        bulk_lookup=False,
        export=False,
        scheduled_searches=0,
    ),
    "professional": Plan(
        id="professional",
        name="Professional",
        monthly_prices={2000: 39, 5000: 99, 10000: 129, 25000: 199},
        discovery_searches_per_day=50,
        max_results_per_search=50,
        bulk_lookup=True,
        export=True,
        scheduled_searches=5,
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        monthly_prices={50000: 349, 100000: 599, 250000: 999, 500000: 1499},
        discovery_searches_per_day=250,
        max_results_per_search=100,
        bulk_lookup=True,
        export=True,
        scheduled_searches=None,
    ),
}


def price_usd(plan: Plan, credits_per_month: int, billing_period: str) -> Decimal:
    """What a plan costs for one billing period, in US dollars — the same
    numbers as the pricing page: yearly is 25% off the monthly price,
    rounded to the dollar per month, times twelve."""
    monthly = Decimal(plan.monthly_prices[credits_per_month])
    if billing_period == "monthly":
        return monthly
    per_month = (monthly * (1 - YEARLY_DISCOUNT)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return per_month * 12
