"""Admin-only user management: view every account, block/unblock access.

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

logger = logging.getLogger("petrolead.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserSchema])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    """Every account, newest first."""
    return list(db.execute(select(User).order_by(User.created_at.desc())).scalars())


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

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    logger.info(
        "Admin %s set is_active=%s for user %s", current_admin.id, payload.is_active, user.id
    )
    return user
