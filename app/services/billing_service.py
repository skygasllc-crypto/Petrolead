"""Plans, email credits and usage limits.

One email credit is spent each time a person lookup — a LinkedIn profile
link, a name + company, or a bulk-lookup line — actually returns a business
email. Company-website extraction and the Email Verifier don't use credits:
neither calls a paid data provider. Plan limits cap company discovery
searches and gate bulk lookup and exports (see `app.services.plans`).

Enforcement is switched on by `BILLING_ENFORCED`; admins are never limited.
Every check raises `BillingError`, which `app.main` turns into an HTTP
error carrying a message the user can act on.
"""

from __future__ import annotations

import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import CreditTransaction, Subscription, User, utcnow
from app.services.plans import PLANS, Plan

logger = logging.getLogger("petrolead.services.billing")

NO_PLAN_MESSAGE = (
    "You don't have an active plan yet. Choose a plan on the Pricing page to start "
    "using PetroLead."
)


class BillingError(Exception):
    """A plan or credit limit stopped the request."""

    def __init__(self, message: str, status_code: int = 402):
        super().__init__(message)
        self.status_code = status_code


def is_exempt(user: User) -> bool:
    """Admins — and everyone, when BILLING_ENFORCED is off — are never limited."""
    return user.is_admin or not get_settings().billing_enforced


def _today() -> str:
    return utcnow().date().isoformat()


def _format_date(value: datetime) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def _record(db: Session, user_id: str, delta: int, reason: str, detail: str, balance: int) -> None:
    db.add(
        CreditTransaction(
            user_id=user_id, delta=delta, reason=reason, detail=detail[:500], balance_after=balance
        )
    )


def renew_if_due(db: Session, subscription: Subscription, *, now: datetime | None = None) -> None:
    """Grant the credits for every monthly period that has started since the
    last renewal. Unused credits roll over, so each grant adds to the balance."""
    now = now or utcnow()
    renewed = False
    while subscription.renews_at <= now:
        subscription.credits_balance += subscription.credits_per_month
        subscription.period_started_at = subscription.renews_at
        subscription.renews_at = subscription.renews_at + relativedelta(months=1)
        _record(
            db,
            subscription.user_id,
            subscription.credits_per_month,
            "monthly_renewal",
            f"{subscription.plan} plan renewed",
            subscription.credits_balance,
        )
        renewed = True
    if renewed:
        db.commit()


def get_subscription(db: Session, user: User) -> Subscription | None:
    subscription = db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    if subscription is not None:
        renew_if_due(db, subscription)
    return subscription


def require_plan(db: Session, user: User) -> tuple[Subscription, Plan] | None:
    """The user's subscription and plan, or None when they're exempt from limits."""
    if is_exempt(user):
        return None
    subscription = get_subscription(db, user)
    if subscription is None or subscription.plan not in PLANS:
        raise BillingError(NO_PLAN_MESSAGE, 402)
    return subscription, PLANS[subscription.plan]


def require_feature(db: Session, user: User, feature: str, label: str) -> None:
    """Raise unless the user's plan includes `feature` (a boolean `Plan` field)."""
    active = require_plan(db, user)
    if active is not None and not getattr(active[1], feature):
        raise BillingError(
            f"{label} isn't included in the {active[1].name} plan. Upgrade to Professional "
            "or Enterprise to use it.",
            403,
        )


def require_credits(db: Session, user: User, needed: int = 1) -> None:
    """Raise unless the user has at least `needed` credits — checked before a
    lookup runs, so nobody spends provider calls they can't pay for."""
    active = require_plan(db, user)
    if active is None:
        return
    subscription = active[0]
    balance = subscription.credits_balance
    if balance >= needed:
        return
    if balance == 0:
        raise BillingError(
            "You're out of email credits. They renew on "
            f"{_format_date(subscription.renews_at)}, or upgrade your plan for more.",
            402,
        )
    raise BillingError(
        f"This lookup needs up to {needed} email credits, but you have {balance}. Look up "
        "fewer people at once, or upgrade your plan for more.",
        402,
    )


def spend_credits(db: Session, user: User, count: int, detail: str) -> None:
    """Deduct `count` credits for found emails.

    A conditional UPDATE keeps two concurrent lookups from pushing the
    balance below zero; if the balance ran short in between, what's left is
    spent instead."""
    if count <= 0 or is_exempt(user):
        return
    spent = db.execute(
        update(Subscription)
        .where(Subscription.user_id == user.id, Subscription.credits_balance >= count)
        .values(credits_balance=Subscription.credits_balance - count)
    )
    if spent.rowcount == 0:
        logger.warning("User %s had fewer than %d credits left when spending", user.id, count)
        db.execute(
            update(Subscription).where(Subscription.user_id == user.id).values(credits_balance=0)
        )
    balance = db.execute(
        select(Subscription.credits_balance).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    if balance is None:
        db.rollback()
        return
    _record(db, user.id, -count, "email_found", detail, balance)
    db.commit()


def check_discovery(db: Session, user: User, requested_results: int) -> None:
    """Raise if a company discovery search would exceed the plan's limits."""
    active = require_plan(db, user)
    if active is None:
        return
    subscription, plan = active
    if requested_results > plan.max_results_per_search:
        raise BillingError(
            f"The {plan.name} plan returns up to {plan.max_results_per_search} results per "
            "search. Choose a smaller number, or upgrade for more.",
            403,
        )
    used = subscription.discovery_searches_today if subscription.discovery_day == _today() else 0
    if used >= plan.discovery_searches_per_day:
        raise BillingError(
            f"You've used all {plan.discovery_searches_per_day} company searches included in "
            f"the {plan.name} plan today. They reset at midnight UTC, or upgrade for more.",
            429,
        )


def check_saved_search_quota(db: Session, user: User, existing: int) -> None:
    """Raise if the user can't create another scheduled search on their plan."""
    active = require_plan(db, user)
    if active is None:
        return
    plan = active[1]
    if plan.scheduled_searches is None:
        return
    if plan.scheduled_searches == 0:
        raise BillingError(
            f"Scheduled searches aren't included in the {plan.name} plan. Upgrade to "
            "Professional or Enterprise to use them.",
            403,
        )
    if existing >= plan.scheduled_searches:
        raise BillingError(
            f"The {plan.name} plan includes up to {plan.scheduled_searches} scheduled searches, "
            "and you've used them all. Delete one first, or upgrade to Enterprise for unlimited "
            "scheduled searches.",
            403,
        )


def allows_scheduled_searches(db: Session, user: User) -> bool:
    """Whether scheduled searches owned by `user` may run right now."""
    if is_exempt(user):
        return True
    subscription = get_subscription(db, user)
    plan = PLANS.get(subscription.plan) if subscription else None
    return plan is not None and plan.scheduled_searches != 0


def record_discovery(db: Session, user: User) -> None:
    """Count one completed discovery search against today's allowance."""
    if is_exempt(user):
        return
    subscription = get_subscription(db, user)
    if subscription is None:
        return
    today = _today()
    if subscription.discovery_day != today:
        subscription.discovery_day = today
        subscription.discovery_searches_today = 0
    subscription.discovery_searches_today += 1
    db.commit()


def assign_plan(
    db: Session, user: User, plan_id: str, credits_per_month: int, *, admin: User
) -> Subscription:
    """Put a user on a plan (an admin action until online payments exist).

    A new subscription starts its first monthly period now and grants that
    month's credits. Changing an existing subscription's plan or tier keeps
    the current balance and renewal date — add credits separately if needed.
    """
    plan = PLANS.get(plan_id)
    if plan is None:
        raise ValueError(f"Unknown plan {plan_id!r}.")
    if credits_per_month not in plan.credit_tiers:
        tiers = ", ".join(f"{tier:,}" for tier in plan.credit_tiers)
        raise ValueError(f"The {plan.name} plan comes with {tiers} credits per month.")

    subscription = get_subscription(db, user)
    if subscription is None:
        now = utcnow()
        subscription = Subscription(
            user_id=user.id,
            plan=plan.id,
            credits_per_month=credits_per_month,
            credits_balance=credits_per_month,
            period_started_at=now,
            renews_at=now + relativedelta(months=1),
        )
        db.add(subscription)
        _record(
            db,
            user.id,
            credits_per_month,
            "plan_started",
            f"{plan.name} plan ({credits_per_month:,}/month) assigned by {admin.email}",
            credits_per_month,
        )
    else:
        subscription.plan = plan.id
        subscription.credits_per_month = credits_per_month
        _record(
            db,
            user.id,
            0,
            "plan_changed",
            f"Changed to {plan.name} ({credits_per_month:,}/month) by {admin.email}",
            subscription.credits_balance,
        )
    db.commit()
    db.refresh(subscription)
    logger.info("Admin %s put user %s on %s/%d", admin.id, user.id, plan.id, credits_per_month)
    return subscription


def remove_plan(db: Session, user: User, *, admin: User) -> None:
    """Take a user off their plan; any remaining credits go with it."""
    subscription = get_subscription(db, user)
    if subscription is None:
        return
    _record(
        db,
        user.id,
        -subscription.credits_balance,
        "plan_removed",
        f"{subscription.plan} plan removed by {admin.email}",
        0,
    )
    db.delete(subscription)
    db.commit()
    logger.info("Admin %s removed the plan for user %s", admin.id, user.id)


def adjust_credits(
    db: Session, user: User, amount: int, note: str | None, *, admin: User
) -> Subscription:
    """Add (positive) or remove (negative) credits; the balance never goes below zero."""
    subscription = get_subscription(db, user)
    if subscription is None:
        raise ValueError("This user has no plan. Assign a plan before adjusting credits.")
    new_balance = max(0, subscription.credits_balance + amount)
    delta = new_balance - subscription.credits_balance
    subscription.credits_balance = new_balance
    detail = f"Adjusted by {admin.email}" + (f": {note}" if note else "")
    _record(db, user.id, delta, "admin_adjustment", detail, new_balance)
    db.commit()
    db.refresh(subscription)
    return subscription


def summary(db: Session, user: User) -> dict:
    """The user's plan, credits and today's usage, for the in-app billing page."""
    subscription = get_subscription(db, user)
    plan = PLANS.get(subscription.plan) if subscription else None
    searches_today = (
        subscription.discovery_searches_today
        if subscription and subscription.discovery_day == _today()
        else 0
    )
    return {
        "exempt": is_exempt(user),
        "plan": plan.id if plan else None,
        "plan_name": plan.name if plan else None,
        "credits_balance": subscription.credits_balance if subscription else 0,
        "credits_per_month": subscription.credits_per_month if subscription else None,
        "renews_at": subscription.renews_at if subscription else None,
        "discovery_searches_today": searches_today,
        "discovery_searches_per_day": plan.discovery_searches_per_day if plan else None,
        "max_results_per_search": plan.max_results_per_search if plan else None,
        "bulk_lookup": plan.bulk_lookup if plan else False,
        "export": plan.export if plan else False,
        "scheduled_searches": plan.scheduled_searches if plan else 0,
    }
