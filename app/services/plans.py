"""Plan catalogue: credit tiers and usage limits for each paid plan.

Mirrors the public pricing page (`frontend/src/components/marketing/pricing.js`)
— keep the two in sync when prices or limits change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    # Monthly email-credit amounts a subscription on this plan can have.
    credit_tiers: tuple[int, ...]
    discovery_searches_per_day: int
    max_results_per_search: int
    bulk_lookup: bool
    export: bool


PLANS: dict[str, Plan] = {
    "basic": Plan(
        id="basic",
        name="Basic",
        credit_tiers=(1000,),
        discovery_searches_per_day=5,
        max_results_per_search=10,
        bulk_lookup=False,
        export=False,
    ),
    "professional": Plan(
        id="professional",
        name="Professional",
        credit_tiers=(2000, 5000, 10000, 25000),
        discovery_searches_per_day=50,
        max_results_per_search=50,
        bulk_lookup=True,
        export=True,
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        credit_tiers=(50000, 100000, 250000, 500000),
        discovery_searches_per_day=250,
        max_results_per_search=100,
        bulk_lookup=True,
        export=True,
    ),
}
