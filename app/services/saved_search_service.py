"""Saved / scheduled searches (Phase 10).

Manages `SavedSearch` rows (CRUD) and running whichever ones are due.
The API layer only ever schedules; actual execution happens either via
`app.worker`'s Celery beat task (production) or by calling
`run_due_saved_searches` directly (tests, or a manual trigger).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import SavedSearch, utcnow
from app.schemas import DiscoverRequestSchema, SavedSearchCreateSchema
from app.services.company_service import run_discovery

logger = logging.getLogger("petrolead.services.saved_search")

FREQUENCY_DELTAS: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


def create_saved_search(db: Session, payload: SavedSearchCreateSchema) -> SavedSearch:
    saved = SavedSearch(
        name=payload.name,
        region=payload.region,
        country=payload.country,
        city=payload.city,
        industry=payload.industry,
        activity=payload.activity,
        products=payload.products,
        keywords=payload.keywords,
        result_limit=payload.limit,
        frequency=payload.frequency,
        is_active=True,
        next_run_at=utcnow(),  # due immediately; first run picks it up on the next check
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    logger.info("Saved search %s (%r) created, frequency=%s", saved.id, saved.name, saved.frequency)
    return saved


def list_saved_searches(db: Session) -> list[SavedSearch]:
    stmt = select(SavedSearch).order_by(SavedSearch.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_saved_search(db: Session, saved_search_id: str) -> SavedSearch | None:
    return db.get(SavedSearch, saved_search_id)


def delete_saved_search(db: Session, saved_search_id: str) -> bool:
    saved = db.get(SavedSearch, saved_search_id)
    if saved is None:
        return False
    db.delete(saved)
    db.commit()
    return True


def set_saved_search_active(
    db: Session, saved_search_id: str, is_active: bool
) -> SavedSearch | None:
    saved = db.get(SavedSearch, saved_search_id)
    if saved is None:
        return None
    saved.is_active = is_active
    db.commit()
    db.refresh(saved)
    return saved


def due_saved_searches(db: Session) -> list[SavedSearch]:
    now = utcnow()
    stmt = select(SavedSearch).where(
        SavedSearch.is_active.is_(True), SavedSearch.next_run_at <= now
    )
    return list(db.execute(stmt).scalars().all())


async def run_saved_search(db: Session, saved: SavedSearch) -> None:
    payload = DiscoverRequestSchema(
        region=saved.region,
        country=saved.country,
        city=saved.city,
        industry=saved.industry,
        activity=saved.activity,
        products=saved.products,
        keywords=saved.keywords,
        limit=saved.result_limit,
    )
    search_query = await run_discovery(db, payload)
    search_query.saved_search_id = saved.id
    saved.last_run_at = utcnow()
    saved.next_run_at = saved.last_run_at + FREQUENCY_DELTAS.get(
        saved.frequency, timedelta(days=1)
    )
    db.commit()
    logger.info(
        "Saved search %s (%r) ran: search_id=%s next_run_at=%s",
        saved.id,
        saved.name,
        search_query.id,
        saved.next_run_at,
    )


async def run_due_saved_searches(db: Session) -> int:
    """Run every saved search whose schedule is currently due. Returns the count run."""
    due = due_saved_searches(db)
    for saved in due:
        try:
            await run_saved_search(db, saved)
        except Exception:
            logger.exception("Scheduled search %s (%r) failed", saved.id, saved.name)
    return len(due)
