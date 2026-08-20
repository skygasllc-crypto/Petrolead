"""Extracted-emails endpoints: a cross-company folder of every business
email PetroLead has found, with its own filtering and CSV/Excel export."""

from __future__ import annotations

import io
import logging

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas import PaginatedEmailsSchema
from app.services import email_service

logger = logging.getLogger("petrolead.api.emails")

router = APIRouter(tags=["emails"])


@router.get("/emails", response_model=PaginatedEmailsSchema)
def get_emails(
    search: str | None = None,
    is_valid: bool | None = None,
    country: str | None = None,
    industry: str | None = None,
    has_exported: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedEmailsSchema:
    try:
        items, total = email_service.list_emails(
            db,
            search=search,
            is_valid=is_valid,
            country=country,
            industry=industry,
            has_exported=has_exported,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.exception("Failed to list emails")
        raise HTTPException(status_code=500, detail="Unable to load emails right now.") from exc

    return PaginatedEmailsSchema(items=items, total=total, page=page, page_size=page_size)


@router.get("/emails/export")
def export_emails(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    search: str | None = None,
    is_valid: bool | None = None,
    country: str | None = None,
    industry: str | None = None,
    has_exported: bool | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export emails matching the given filters as CSV or Excel.

    Every exported email is stamped with `exported_at` so it can be told
    apart from fresh, not-yet-exported ones (`has_exported=false` filter).
    """
    try:
        emails = email_service.export_emails(
            db,
            search=search,
            is_valid=is_valid,
            country=country,
            industry=industry,
            has_exported=has_exported,
        )
        df = pd.DataFrame(email_service.to_export_rows(emails))
    except Exception as exc:
        logger.exception("Failed to export emails")
        raise HTTPException(
            status_code=500, detail="Unable to export emails right now."
        ) from exc

    buffer = io.BytesIO()
    if format == "xlsx":
        df.to_excel(buffer, index=False, sheet_name="Emails")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "petrolead-emails.xlsx"
    else:
        df.to_csv(buffer, index=False)
        media_type = "text/csv"
        filename = "petrolead-emails.csv"
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
