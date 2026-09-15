"""Paying for a plan in crypto: payment methods, orders and "I have paid"."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas_billing import (
    CreateOrderRequestSchema,
    MarkOrderPaidRequestSchema,
    PaymentMethodSchema,
    PaymentOrderSchema,
)
from app.services import notifications, payment_service

router = APIRouter(prefix="/billing", tags=["payments"])


@router.get("/payment-methods", response_model=list[PaymentMethodSchema])
def list_payment_methods() -> list[dict]:
    """Coins accepted for plans — only those with a receiving address configured."""
    return payment_service.enabled_methods()


@router.post("/orders", response_model=PaymentOrderSchema)
async def create_order(
    payload: CreateOrderRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Start paying for a plan. Returns the address and exact amount to send;
    the price is always taken from the server's plan catalogue."""
    order = await payment_service.create_order(
        db,
        current_user,
        plan_id=payload.plan,
        credits_per_month=payload.credits_per_month,
        billing_period=payload.billing_period,
        currency=payload.currency,
    )
    return payment_service.serialize_order(order)


@router.get("/orders", response_model=list[PaymentOrderSchema])
def list_orders(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    return [
        payment_service.serialize_order(order)
        for order in payment_service.list_user_orders(db, current_user)
    ]


@router.get("/orders/{order_id}", response_model=PaymentOrderSchema)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return payment_service.serialize_order(
        payment_service.get_user_order(db, current_user, order_id)
    )


@router.post("/orders/{order_id}/paid", response_model=PaymentOrderSchema)
def mark_order_paid(
    order_id: str,
    payload: MarkOrderPaidRequestSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """"I have paid": record the transaction ID and notify admins to check it."""
    order = payment_service.submit_order(db, current_user, order_id, payload.tx_hash)
    background_tasks.add_task(
        notifications.notify_payment_submitted,
        payment_service.serialize_order(order, include_customer=True),
        notifications.admin_recipients(db),
    )
    return payment_service.serialize_order(order)


@router.post("/orders/{order_id}/cancel", response_model=PaymentOrderSchema)
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return payment_service.serialize_order(
        payment_service.cancel_order(db, current_user, order_id)
    )
