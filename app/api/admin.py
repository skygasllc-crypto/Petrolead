"""Admin-only user management: view every account, block/unblock access, and
manage each account's plan and email credits.

Every endpoint here requires `is_admin` (enforced at router-inclusion time
in `app.main`, same pattern as the auth-required routers) — see
`app.core.deps.get_current_admin_user`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas_auth import AdminUserSchema, UpdateUserStatusRequestSchema
from app.schemas_billing import AdjustCreditsRequestSchema, AssignPlanRequestSchema
from app.services import billing_service

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
