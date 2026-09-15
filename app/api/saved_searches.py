"""Saved / scheduled search endpoints (Phase 10).

These endpoints only manage the signed-in account's own schedules
(create/list/toggle/delete). Actual execution happens out-of-band via
`app.worker`'s Celery beat task, which checks `next_run_at` — see that
module's docstring for how to run it. `POST /api/saved-searches/run-due` is
provided for manually running your due searches without waiting for a
worker, useful for testing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas import SavedSearchCreateSchema, SavedSearchSchema
from app.services import billing_service, saved_search_service

logger = logging.getLogger("petrolead.api.saved_searches")

router = APIRouter(tags=["saved-searches"])


@router.post("/saved-searches", response_model=SavedSearchSchema)
def create_saved_search(
    payload: SavedSearchCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchSchema:
    """Schedule a search. The number of scheduled searches is limited by plan."""
    existing = saved_search_service.count_saved_searches(db, current_user.id)
    billing_service.check_saved_search_quota(db, current_user, existing)
    try:
        return saved_search_service.create_saved_search(db, payload, current_user.id)
    except Exception as exc:
        logger.exception("Failed to create saved search")
        raise HTTPException(
            status_code=500, detail="Unable to save this search right now."
        ) from exc


@router.get("/saved-searches", response_model=list[SavedSearchSchema])
def list_saved_searches(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[SavedSearchSchema]:
    try:
        return saved_search_service.list_saved_searches(db, current_user.id)
    except Exception as exc:
        logger.exception("Failed to list saved searches")
        raise HTTPException(
            status_code=500, detail="Unable to load saved searches right now."
        ) from exc


@router.patch("/saved-searches/{saved_search_id}", response_model=SavedSearchSchema)
def toggle_saved_search(
    saved_search_id: str,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchSchema:
    saved = saved_search_service.set_saved_search_active(
        db, saved_search_id, is_active, current_user.id
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    return saved


@router.delete("/saved-searches/{saved_search_id}", status_code=204, response_model=None)
def delete_saved_search(
    saved_search_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = saved_search_service.delete_saved_search(db, saved_search_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found.")


@router.post("/saved-searches/run-due")
async def run_due_saved_searches(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    """Manually run whichever of your saved searches are currently due.

    A convenience for environments without a Celery worker running (e.g.
    local development); production should rely on `app.worker`'s beat
    schedule instead of polling this endpoint.
    """
    try:
        count = await saved_search_service.run_due_saved_searches(db, owner_id=current_user.id)
    except Exception as exc:
        logger.exception("Failed to run due saved searches")
        raise HTTPException(
            status_code=500, detail="Unable to run scheduled searches right now."
        ) from exc
    return {"ran": count}
