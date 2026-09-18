"""Extracted-emails endpoints: a cross-company folder of every business
email PetroLead has found, with its own filtering and CSV/Excel export."""

from __future__ import annotations

import io
import logging
from collections import Counter

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.discovery import email_verification as verification
from app.discovery.emails import verify_emails as verify_email_addresses
from app.schemas import PaginatedEmailsSchema, VerifyEmailsRequestSchema, VerifyEmailsResponseSchema
from app.services import billing_service, email_service

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
    current_user: User = Depends(get_current_user),
) -> PaginatedEmailsSchema:
    try:
        items, total = email_service.list_emails(
            db,
            owner_id=current_user.id,
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


@router.post("/emails/verify", response_model=VerifyEmailsResponseSchema)
async def verify_emails(
    payload: VerifyEmailsRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerifyEmailsResponseSchema:
    """Email Verifier: grade each address as deliverable, undeliverable,
    risky or unknown, so undeliverable ones can be dropped before sending.

    Nothing is saved. Syntax, disposable domains and obvious typos are
    decided locally; whether a mailbox actually exists depends on
    `EMAIL_VERIFY_PROVIDER` — with the default (`mx`) only the domain is
    checked, so well-formed addresses come back `risky`, never
    `deliverable`.

    One credit is spent per address a provider actually confirmed. Nothing
    is charged for addresses settled locally (bad syntax, throwaway domain,
    known typo), for domain-only grading, or for a call that failed — those
    cost us nothing, so they cost the customer nothing.
    """
    provider_active = verification.get_provider(get_settings()) is not None
    if provider_active:
        # Checked before running, so an empty balance can't ring up provider
        # fees. What's actually spent is the count of answers received.
        billing_service.require_credits(db, current_user)
    else:
        billing_service.require_plan(db, current_user)

    batch = await verify_email_addresses(payload.emails)
    results = batch.results
    if batch.provider_checked:
        billing_service.spend_credits(
            db,
            current_user,
            batch.provider_checked,
            f"Email Verifier: {batch.provider_checked} mailbox check(s)",
        )
    counts = Counter(result["status"] for result in results)
    return VerifyEmailsResponseSchema(
        results=results,
        deliverable_count=counts["deliverable"],
        undeliverable_count=counts["undeliverable"],
        risky_count=counts["risky"],
        unknown_count=counts["unknown"],
        mailbox_checks_available=provider_active,
    )


@router.get("/emails/export")
def export_emails(
    format: str = Query(default="csv", pattern="^(csv|xlsx|txt)$"),
    search: str | None = None,
    is_valid: bool | None = None,
    country: str | None = None,
    industry: str | None = None,
    has_exported: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Export emails matching the given filters as CSV, Excel or a plain
    text list.

    `txt` is addresses only, one per line — no header row and no other
    columns, because that file exists to be pasted straight into a mail
    tool and a header would arrive as a bogus recipient.

    Every exported email is stamped with `exported_at` so it can be told
    apart from fresh, not-yet-exported ones (`has_exported=false` filter).
    That applies to `txt` too: a format that skipped the stamp would
    quietly break the "Not yet exported" filter.
    """
    billing_service.require_feature(db, current_user, "export", "CSV & Excel export")
    try:
        emails = email_service.export_emails(
            db,
            owner_id=current_user.id,
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
    elif format == "txt":
        # Addresses only, one per line. An empty result must still be a
        # valid (empty) file rather than a KeyError on a column-less frame.
        addresses = df["Email"].tolist() if not df.empty else []
        buffer.write(("\n".join(addresses) + "\n" if addresses else "").encode("utf-8"))
        media_type = "text/plain; charset=utf-8"
        filename = "petrolead-emails.txt"
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
