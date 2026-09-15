"""The signed-in user's plan, credits and usage."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas_billing import BillingSummarySchema
from app.services import billing_service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/me", response_model=BillingSummarySchema)
def get_my_billing(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    return billing_service.summary(db, current_user)
