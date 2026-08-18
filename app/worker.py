"""Celery application for scheduled discovery jobs (Phase 10).

Not required to run PetroLead itself — every other feature (discovery,
contact/email/phone extraction, lead scoring, export) works entirely
through the FastAPI app. This module only matters once you have
*scheduled* searches (created via `POST /api/saved-searches`) that you
want to run automatically instead of triggering manually via
`POST /api/saved-searches/run-due`.

To run it, alongside the API and a Redis instance (`docker compose up
redis`, or point `REDIS_URL` at any reachable Redis):

    celery -A app.worker worker --beat --loglevel=info

The beat schedule checks every 15 minutes for saved searches whose
`next_run_at` has passed and are `is_active`; each one is executed
through the exact same `run_discovery` pipeline a manual search uses, so
results are deduplicated and scored identically either way.
"""

from __future__ import annotations

import asyncio
import logging

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings
from app.core.logging import setup_logging
from app.database.connection import SessionLocal
from app.services.saved_search_service import run_due_saved_searches

setup_logging()
logger = logging.getLogger("petrolead.worker")

settings = get_settings()

celery_app = Celery("petrolead", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "run-due-saved-searches": {
        "task": "app.worker.run_due_saved_searches_task",
        "schedule": crontab(minute="*/15"),
    }
}


@celery_app.task(name="app.worker.run_due_saved_searches_task")
def run_due_saved_searches_task() -> int:
    db = SessionLocal()
    try:
        count = asyncio.run(run_due_saved_searches(db))
        logger.info("Scheduled task: ran %d due saved search(es)", count)
        return count
    finally:
        db.close()
