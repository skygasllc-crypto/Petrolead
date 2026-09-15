"""Saved / scheduled searches (Phase 10).

Manages `SavedSearch` rows (CRUD) and running whichever ones are due.
Every saved search belongs to one account, and its runs save companies
into that account's list. The API layer only ever schedules; actual
execution happens either via `app.worker`'s Celery beat task (production)
or by calling `run_due_saved_searches` directly (tests, or a manual trigger).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import SavedSearch, User, utcnow
from app.schemas import DiscoverRequestSchema, SavedSearchCreateSchema
from app.services import billing_service
from app.services.company_service import run_discovery

logger = logging.getLogger("petrolead.services.saved_search")

FREQUENCY_DELTAS: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


def create_saved_search(
    db: Session, payload: SavedSearchCreateSchema, owner_id: str
) -> SavedSearch:
    saved = SavedSearch(
        owner_id=owner_id,
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


def count_saved_searches(db: Session, owner_id: str) -> int:
    return db.execute(
        select(func.count()).select_from(SavedSearch).where(SavedSearch.owner_id == owner_id)
    ).scalar_one()


def list_saved_searches(db: Session, owner_id: str) -> list[SavedSearch]:
    stmt = (
        select(SavedSearch)
        .where(SavedSearch.owner_id == owner_id)
        .order_by(SavedSearch.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_saved_search(db: Session, saved_search_id: str, owner_id: str) -> SavedSearch | None:
    """One of `owner_id`'s saved searches — another account's is treated as not found."""
    saved = db.get(SavedSearch, saved_search_id)
    return saved if saved is not None and saved.owner_id == owner_id else None


def delete_saved_search(db: Session, saved_search_id: str, owner_id: str) -> bool:
    saved = get_saved_search(db, saved_search_id, owner_id)
    if saved is None:
        return False
    db.delete(saved)
    db.commit()
    return True


def set_saved_search_active(
    db: Session, saved_search_id: str, is_active: bool, owner_id: str
) -> SavedSearch | None:
    saved = get_saved_search(db, saved_search_id, owner_id)
    if saved is None:
        return None
    saved.is_active = is_active
    db.commit()
    db.refresh(saved)
    return saved


def due_saved_searches(db: Session, owner_id: str | None = None) -> list[SavedSearch]:
    """Active saved searches whose next run is due — every account's, or one account's."""
    stmt = select(SavedSearch).where(
        SavedSearch.is_active.is_(True), SavedSearch.next_run_at <= utcnow()
    )
    if owner_id is not None:
        stmt = stmt.where(SavedSearch.owner_id == owner_id)
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
    search_query = await run_discovery(db, payload, saved.owner_id)
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


async def run_due_saved_searches(db: Session, owner_id: str | None = None) -> int:
    """Run every due saved search (or just `owner_id`'s). Returns the count run.

    A search is skipped — and stays due — while its owner is blocked or no
    longer has a plan that includes scheduled searches, so a lapsed plan
    doesn't keep spending search-provider calls."""
    ran = 0
    for saved in due_saved_searches(db, owner_id):
        owner = db.get(User, saved.owner_id)
        if owner is None or not owner.is_active:
            continue
        if not billing_service.allows_scheduled_searches(db, owner):
            logger.info(
                "Skipping scheduled search %s: its owner's plan doesn't include them", saved.id
            )
            continue
        try:
            await run_saved_search(db, saved)
            ran += 1
        except Exception:
            logger.exception("Scheduled search %s (%r) failed", saved.id, saved.name)
    return ran
