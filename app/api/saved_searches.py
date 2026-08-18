"""Saved / scheduled search endpoints (Phase 10).

These endpoints only manage the schedule (create/list/toggle/delete).
Actual execution happens out-of-band via `app.worker`'s Celery beat task,
which checks `next_run_at` — see that module's docstring for how to run
it. `POST /api/saved-searches/{id}/run-now` is provided for manually
triggering a due check without waiting for a worker, useful for testing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas import SavedSearchCreateSchema, SavedSearchSchema
from app.services import saved_search_service

logger = logging.getLogger("petrolead.api.saved_searches")

router = APIRouter(tags=["saved-searches"])


@router.post("/saved-searches", response_model=SavedSearchSchema)
def create_saved_search(
    payload: SavedSearchCreateSchema, db: Session = Depends(get_db)
) -> SavedSearchSchema:
    try:
        return saved_search_service.create_saved_search(db, payload)
    except Exception as exc:
        logger.exception("Failed to create saved search")
        raise HTTPException(
            status_code=500, detail="Unable to save this search right now."
        ) from exc


@router.get("/saved-searches", response_model=list[SavedSearchSchema])
def list_saved_searches(db: Session = Depends(get_db)) -> list[SavedSearchSchema]:
    try:
        return saved_search_service.list_saved_searches(db)
    except Exception as exc:
        logger.exception("Failed to list saved searches")
        raise HTTPException(
            status_code=500, detail="Unable to load saved searches right now."
        ) from exc


@router.patch("/saved-searches/{saved_search_id}", response_model=SavedSearchSchema)
def toggle_saved_search(
    saved_search_id: str, is_active: bool, db: Session = Depends(get_db)
) -> SavedSearchSchema:
    saved = saved_search_service.set_saved_search_active(db, saved_search_id, is_active)
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    return saved


@router.delete("/saved-searches/{saved_search_id}", status_code=204, response_model=None)
def delete_saved_search(saved_search_id: str, db: Session = Depends(get_db)) -> None:
    deleted = saved_search_service.delete_saved_search(db, saved_search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found.")


@router.post("/saved-searches/run-due")
async def run_due_saved_searches(db: Session = Depends(get_db)) -> dict:
    """Manually run whichever saved searches are currently due.

    A convenience for environments without a Celery worker running (e.g.
    local development); production should rely on `app.worker`'s beat
    schedule instead of polling this endpoint.
    """
    try:
        count = await saved_search_service.run_due_saved_searches(db)
    except Exception as exc:
        logger.exception("Failed to run due saved searches")
        raise HTTPException(
            status_code=500, detail="Unable to run scheduled searches right now."
        ) from exc
    return {"ran": count}
