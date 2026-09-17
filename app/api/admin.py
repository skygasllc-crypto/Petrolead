"""Admin-only user management: view every account, block/unblock access,
manage each account's plan and email credits, and review crypto payments.

Every endpoint here requires `is_admin` (enforced at router-inclusion time
in `app.main`, same pattern as the auth-required routers) — see
`app.core.deps.get_current_admin_user`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas_auth import AdminUserSchema, UpdateUserStatusRequestSchema
from app.schemas_billing import (
    AdjustCreditsRequestSchema,
    AdminPaymentOrderSchema,
    AssignPlanRequestSchema,
    ConfirmPaymentRequestSchema,
    RejectPaymentRequestSchema,
)
from app.services import billing_service, payment_service

logger = logging.getLogger("petrolead.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.get("/users", response_model=list[AdminUserSchema])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    """Every account, newest first, with its plan and current credit balance."""
    users = list(db.execute(select(User).order_by(User.created_at.desc())).scalars())
    for user in users:
        if user.subscription is not None:
            billing_service.renew_if_due(db, user.subscription)
    return users


@router.patch("/users/{user_id}", response_model=AdminUserSchema)
def update_user_status(
    user_id: str,
    payload: UpdateUserStatusRequestSchema,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> User:
    """Block (`is_active=false`) or unblock a user. Takes effect
    immediately, not just on their next login — every authenticated
    request re-checks `is_active` against the database (see
    `app.core.deps.get_current_user`), so a blocked user's existing token
    stops working on their very next request."""
    if user_id == current_admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="You can't block your own account.")

    user = _get_user_or_404(db, user_id)
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    logger.info(
        "Admin %s set is_active=%s for user %s", current_admin.id, payload.is_active, user.id
    )
    return user


@router.post("/users/{user_id}/revoke-sessions", response_model=AdminUserSchema)
def revoke_user_sessions(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> User:
    """End every session for an account without blocking it — for when a
    token may have been stolen but the customer has done nothing wrong.
    Their next request fails and they simply log in again; blocking, by
    contrast, locks them out until an admin unblocks them."""
    user = _get_user_or_404(db, user_id)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    logger.info("Admin %s ended every session for user %s", current_admin.id, user.id)
    return user


@router.put("/users/{user_id}/subscription", response_model=AdminUserSchema)
def set_user_plan(
    user_id: str,
    payload: AssignPlanRequestSchema,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> User:
    """Put a user on a plan and credit tier. A user without a plan gets the
    first month's credits straight away; changing an existing plan keeps
    their balance and renewal date."""
    user = _get_user_or_404(db, user_id)
    try:
        billing_service.assign_plan(
            db, user, payload.plan, payload.credits_per_month, admin=current_admin
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(user)
    return user


@router.delete("/users/{user_id}/subscription", response_model=AdminUserSchema)
def remove_user_plan(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> User:
    """Take a user off their plan. Their remaining credits are removed too."""
    user = _get_user_or_404(db, user_id)
    billing_service.remove_plan(db, user, admin=current_admin)
    db.refresh(user)
    return user


@router.post("/users/{user_id}/credits", response_model=AdminUserSchema)
def adjust_user_credits(
    user_id: str,
    payload: AdjustCreditsRequestSchema,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> User:
    """Add (positive `amount`) or remove (negative) email credits. The
    balance never drops below zero; every change is kept in the credit history."""
    user = _get_user_or_404(db, user_id)
    try:
        billing_service.adjust_credits(db, user, payload.amount, payload.note, admin=current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(user)
    return user


_ORDER_STATUS_PATTERN = "^(" + "|".join(payment_service.ORDER_STATUSES) + ")$"


@router.get("/payments", response_model=list[AdminPaymentOrderSchema])
def list_payments(
    status: str | None = Query(default=None, pattern=_ORDER_STATUS_PATTERN),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Crypto payment orders, newest first — `status=submitted` for the ones to check."""
    return [
        payment_service.serialize_order(order, include_customer=True)
        for order in payment_service.list_orders_for_admin(db, status)
    ]


@router.get("/payments/pending-count")
def pending_payments_count(db: Session = Depends(get_db)) -> dict:
    """How many payments customers have marked paid that are waiting for a decision."""
    return {"count": payment_service.pending_count(db)}


@router.post("/payments/{order_id}/confirm", response_model=AdminPaymentOrderSchema)
def confirm_payment(
    order_id: str,
    payload: ConfirmPaymentRequestSchema,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> dict:
    """Confirm a payment after checking the receiving address on the block
    explorer. Starts, renews or changes the customer's plan straight away;
    an optional `tx_hash` records the transaction you matched."""
    order = payment_service.confirm_order(
        db, order_id, admin=current_admin, note=payload.note, tx_hash=payload.tx_hash
    )
    return payment_service.serialize_order(order, include_customer=True)


@router.post("/payments/{order_id}/reject", response_model=AdminPaymentOrderSchema)
def reject_payment(
    order_id: str,
    payload: RejectPaymentRequestSchema,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
) -> dict:
    """Reject a payment that didn't arrive or doesn't match. The note is shown to the customer."""
    order = payment_service.reject_order(db, order_id, admin=current_admin, note=payload.note)
    return payment_service.serialize_order(order, include_customer=True)
