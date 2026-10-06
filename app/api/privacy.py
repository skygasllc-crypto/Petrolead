"""Opt-out: anyone can have their address removed from the contact
directory, and it is never stored there again. No account needed — the
people in the directory aren't customers."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services import contact_directory

logger = logging.getLogger("petrolead.api.privacy")

router = APIRouter(prefix="/privacy", tags=["privacy"])


class OptOutRequestSchema(BaseModel):
    email: EmailStr


@router.post("/opt-out", status_code=202)
def opt_out(payload: OptOutRequestSchema, db: Session = Depends(get_db)) -> dict:
    """Remove an address from the directory and refuse it from now on. The
    answer is the same whether or not it was there, so this can't be used
    to find out who's in the directory."""
    contact_directory.suppress(db, payload.email)
    logger.info("An address was opted out of the contact directory")
    return {"detail": "Done. This address has been removed and won't be stored again."}
