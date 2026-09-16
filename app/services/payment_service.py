"""Crypto payments for plans, confirmed by an admin.

1. A customer creates an order for a plan, credit tier and billing period,
   paying in BTC, USDT (TRC-20) or TRX. The order records the business's
   receiving address (from settings) and the exact amount to send — BTC and
   TRX amounts come from a live price quote held for `CRYPTO_QUOTE_MINUTES`.
2. The customer sends the coins and clicks "I have paid" — nothing to type.
   Each order carries a reference code the app generates (BTC and TRC-20
   transfers have no memo field, so it identifies the order here, not on the
   blockchain). A transaction ID is optional, from either side.
3. An admin checks the receiving address on a block explorer — matching the
   amount and time — and confirms the payment, which starts, renews or
   changes the customer's plan, or rejects it with a note the customer sees.

No payment processor, wallet software or private keys are involved: the app
only ever shows public receiving addresses.
"""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_UP, Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import PaymentOrder, User, utcnow
from app.services import billing_service
from app.services.crypto_rates import RateUnavailableError, usd_price
from app.services.plans import BILLING_PERIOD_MONTHS, PLANS, price_usd

logger = logging.getLogger("petrolead.services.payment")

AWAITING_PAYMENT = "awaiting_payment"
SUBMITTED = "submitted"
CONFIRMED = "confirmed"
REJECTED = "rejected"
CANCELLED = "cancelled"
EXPIRED = "expired"
ORDER_STATUSES = (AWAITING_PAYMENT, SUBMITTED, CONFIRMED, REJECTED, CANCELLED, EXPIRED)

# A USDT price never moves, so those orders get a full day to be paid.
USDT_ORDER_MINUTES = 24 * 60

# Bitcoin and TRON transaction IDs are both 64 hexadecimal characters.
TX_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Reference codes skip look-alike characters (no O/0, I/1) so they're easy to
# read out over the phone or in an email.
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_reference(db: Session) -> str:
    """A short code identifying this order, e.g. PL-7K3D9A2M."""
    for _ in range(5):
        reference = "PL-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(8))
        taken = db.execute(
            select(PaymentOrder.id).where(PaymentOrder.reference == reference)
        ).first()
        if not taken:
            return reference
    raise PaymentError("Couldn't start this payment. Please try again.", 503)


@dataclass(frozen=True)
class CryptoMethod:
    currency: str
    symbol: str
    name: str
    network: str
    decimals: int
    address_setting: str
    explorer_tx_url: str


METHODS: dict[str, CryptoMethod] = {
    "BTC": CryptoMethod(
        currency="BTC",
        symbol="BTC",
        name="Bitcoin",
        network="Bitcoin",
        decimals=8,
        address_setting="crypto_btc_address",
        explorer_tx_url="https://mempool.space/tx/{tx}",
    ),
    "USDT_TRC20": CryptoMethod(
        currency="USDT_TRC20",
        symbol="USDT",
        name="Tether (USDT)",
        network="TRON (TRC-20)",
        decimals=6,
        address_setting="crypto_usdt_trc20_address",
        explorer_tx_url="https://tronscan.org/#/transaction/{tx}",
    ),
    "TRX": CryptoMethod(
        currency="TRX",
        symbol="TRX",
        name="TRON (TRX)",
        network="TRON",
        decimals=6,
        address_setting="crypto_trx_address",
        explorer_tx_url="https://tronscan.org/#/transaction/{tx}",
    ),
}


class PaymentError(Exception):
    """A payment request couldn't be carried out; the message is shown to the user."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def enabled_methods() -> list[dict]:
    """The coins customers can pay with — those with a receiving address set."""
    settings = get_settings()
    return [
        {
            "currency": method.currency,
            "symbol": method.symbol,
            "name": method.name,
            "network": method.network,
            "address": getattr(settings, method.address_setting),
        }
        for method in METHODS.values()
        if getattr(settings, method.address_setting)
    ]


def serialize_order(order: PaymentOrder, *, include_customer: bool = False) -> dict:
    method = METHODS[order.currency]
    plan = PLANS.get(order.plan)
    data = {
        "id": order.id,
        "reference": order.reference,
        "plan": order.plan,
        "plan_name": plan.name if plan else order.plan,
        "credits_per_month": order.credits_per_month,
        "billing_period": order.billing_period,
        "amount_usd": f"{order.amount_usd_cents / 100:.2f}",
        "currency": order.currency,
        "coin_symbol": method.symbol,
        "coin_name": method.name,
        "network": method.network,
        "pay_address": order.pay_address,
        "amount_crypto": order.amount_crypto,
        "usd_rate": order.usd_rate,
        "status": order.status,
        "tx_hash": order.tx_hash,
        "explorer_url": method.explorer_tx_url.format(tx=order.tx_hash) if order.tx_hash else None,
        "admin_note": order.admin_note,
        "created_at": order.created_at,
        "expires_at": order.expires_at,
        "submitted_at": order.submitted_at,
        "reviewed_at": order.reviewed_at,
    }
    if include_customer:
        data["customer_email"] = order.user.email
        data["paid_after_quote_expired"] = bool(
            order.submitted_at and order.submitted_at > order.expires_at
        )
    return data


async def create_order(
    db: Session,
    user: User,
    *,
    plan_id: str,
    credits_per_month: int,
    billing_period: str,
    currency: str,
) -> PaymentOrder:
    settings = get_settings()
    plan = PLANS.get(plan_id)
    if plan is None or credits_per_month not in plan.credit_tiers:
        raise PaymentError("That plan isn't available. Choose a plan on the Pricing page.")
    if billing_period not in BILLING_PERIOD_MONTHS:
        raise PaymentError("Choose monthly or yearly billing.")
    method = METHODS.get(currency)
    address = getattr(settings, method.address_setting) if method else None
    if not address:
        raise PaymentError("That payment method isn't available.")

    amount_usd = price_usd(plan, credits_per_month, billing_period)
    now = utcnow()
    if currency == "USDT_TRC20":
        rate = None
        amount = amount_usd.quantize(Decimal("0.01"))
        expires_at = now + timedelta(minutes=USDT_ORDER_MINUTES)
    else:
        try:
            rate = await usd_price(currency, settings=settings)
        except RateUnavailableError as exc:
            raise PaymentError(
                f"We couldn't get the current {method.name} price. Try again in a minute, "
                "or pay with USDT.",
                503,
            ) from exc
        # Round up, so the business never receives less than the plan costs.
        step = Decimal(1).scaleb(-method.decimals)
        amount = (amount_usd / rate).quantize(step, rounding=ROUND_UP)
        expires_at = now + timedelta(minutes=settings.crypto_quote_minutes)

    order = PaymentOrder(
        user_id=user.id,
        reference=_new_reference(db),
        plan=plan.id,
        credits_per_month=credits_per_month,
        billing_period=billing_period,
        amount_usd_cents=int(amount_usd * 100),
        currency=currency,
        pay_address=address,
        amount_crypto=format(amount, "f"),
        usd_rate=format(rate, "f") if rate is not None else None,
        status=AWAITING_PAYMENT,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    logger.info(
        "Payment order %s created: user=%s plan=%s/%d %s %s %s",
        order.reference,
        user.id,
        plan.id,
        credits_per_month,
        billing_period,
        order.amount_crypto,
        currency,
    )
    return order


def expire_stale_orders(db: Session) -> None:
    """Mark unpaid orders whose price quote has lapsed as expired."""
    db.execute(
        update(PaymentOrder)
        .where(PaymentOrder.status == AWAITING_PAYMENT, PaymentOrder.expires_at <= utcnow())
        .values(status=EXPIRED)
    )
    db.commit()


def get_user_order(db: Session, user: User, order_id: str) -> PaymentOrder:
    expire_stale_orders(db)
    order = db.get(PaymentOrder, order_id)
    if order is None or order.user_id != user.id:
        raise PaymentError("Order not found.", 404)
    return order


def list_user_orders(db: Session, user: User) -> list[PaymentOrder]:
    expire_stale_orders(db)
    stmt = (
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def _clean_tx_hash(db: Session, order: PaymentOrder, tx_hash: str) -> str:
    """Check an optional transaction ID: right shape, and not already claimed."""
    tx_hash = tx_hash.strip().lower()
    if not TX_HASH_RE.match(tx_hash):
        raise PaymentError(
            "That doesn't look like a transaction ID. It's a 64-character code shown in your "
            "wallet or exchange once the payment is sent — or leave it out."
        )
    already_used = db.execute(
        select(PaymentOrder.id).where(PaymentOrder.tx_hash == tx_hash, PaymentOrder.id != order.id)
    ).first()
    if already_used:
        raise PaymentError("This transaction ID has already been used for another order.", 409)
    return tx_hash


def submit_order(
    db: Session, user: User, order_id: str, tx_hash: str | None = None
) -> PaymentOrder:
    """The customer's "I have paid" — nothing to type. A transaction ID is
    optional and only helps an admin find the payment faster.

    An expired quote can still be marked paid — the coins may already be on
    their way — and the admin sees that it expired."""
    order = get_user_order(db, user, order_id)
    if order.status not in (AWAITING_PAYMENT, EXPIRED):
        raise PaymentError("This order has already been marked as paid or closed.", 409)

    if tx_hash and tx_hash.strip():
        order.tx_hash = _clean_tx_hash(db, order, tx_hash)
    order.status = SUBMITTED
    order.submitted_at = utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PaymentError(
            "This transaction ID has already been used for another order.", 409
        ) from exc
    db.refresh(order)
    logger.info("Payment order %s marked paid by user %s", order.reference, user.id)
    return order


def cancel_order(db: Session, user: User, order_id: str) -> PaymentOrder:
    order = get_user_order(db, user, order_id)
    if order.status not in (AWAITING_PAYMENT, EXPIRED):
        raise PaymentError("Only an order that hasn't been marked paid can be cancelled.", 409)
    order.status = CANCELLED
    db.commit()
    db.refresh(order)
    return order


def pending_count(db: Session) -> int:
    return db.execute(
        select(func.count()).select_from(PaymentOrder).where(PaymentOrder.status == SUBMITTED)
    ).scalar_one()


def list_orders_for_admin(db: Session, status: str | None = None) -> list[PaymentOrder]:
    expire_stale_orders(db)
    stmt = select(PaymentOrder).order_by(PaymentOrder.created_at.desc())
    if status:
        stmt = stmt.where(PaymentOrder.status == status)
    return list(db.execute(stmt).scalars().all())


def _order_to_review(db: Session, order_id: str) -> PaymentOrder:
    order = db.get(PaymentOrder, order_id)
    if order is None:
        raise PaymentError("Payment not found.", 404)
    if order.status != SUBMITTED:
        raise PaymentError("Only a payment the customer has marked as paid can be reviewed.", 409)
    return order


def confirm_order(
    db: Session, order_id: str, *, admin: User, note: str | None, tx_hash: str | None = None
) -> PaymentOrder:
    """Confirm a checked payment: start, renew or change the customer's plan.
    An admin can record the transaction ID they found while checking."""
    order = _order_to_review(db, order_id)
    if tx_hash and tx_hash.strip():
        order.tx_hash = _clean_tx_hash(db, order, tx_hash)
    customer = db.get(User, order.user_id)
    billing_service.activate_paid_plan(
        db,
        customer,
        plan_id=order.plan,
        credits_per_month=order.credits_per_month,
        months=BILLING_PERIOD_MONTHS[order.billing_period],
        detail=f"Crypto payment {order.reference} confirmed by {admin.email}",
    )
    order.status = CONFIRMED
    order.reviewed_at = utcnow()
    order.reviewed_by_id = admin.id
    order.admin_note = note
    db.commit()
    db.refresh(order)
    logger.info("Admin %s confirmed payment order %s", admin.id, order.reference)
    return order


def reject_order(db: Session, order_id: str, *, admin: User, note: str) -> PaymentOrder:
    order = _order_to_review(db, order_id)
    order.status = REJECTED
    order.reviewed_at = utcnow()
    order.reviewed_by_id = admin.id
    order.admin_note = note
    db.commit()
    db.refresh(order)
    logger.info("Admin %s rejected payment order %s", admin.id, order.reference)
    return order
