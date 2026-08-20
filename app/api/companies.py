"""Company discovery API endpoints."""

from __future__ import annotations

import io
import logging
import math

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import SearchStatus
from app.schemas import (
    BulkContactLookupRequestSchema,
    BulkContactLookupResponseSchema,
    BulkContactLookupResultSchema,
    CompanyDetailSchema,
    DiscoveredCompanyPreviewSchema,
    DiscoverRequestSchema,
    DiscoverResponseSchema,
    DiscoverUrlRequestSchema,
    PaginatedCompaniesSchema,
    SaveCompaniesBulkRequestSchema,
    SaveCompaniesBulkResponseSchema,
    SaveCompanyRequestSchema,
    SearchQuerySchema,
)
from app.services import company_service

logger = logging.getLogger("petrolead.api.companies")

router = APIRouter(tags=["companies"])


@router.get("/companies", response_model=PaginatedCompaniesSchema)
def get_companies(
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = Query(default=None, ge=0, le=100),
    min_lead_score: int | None = Query(default=None, ge=0, le=100),
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_exported: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedCompaniesSchema:
    try:
        items, total = company_service.list_companies(
            db,
            country=country,
            region=region,
            industry=industry,
            product=product,
            min_relevance=min_relevance,
            min_lead_score=min_lead_score,
            has_email=has_email,
            has_phone=has_phone,
            has_exported=has_exported,
            search=search,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.exception("Failed to list companies")
        raise HTTPException(
            status_code=500, detail="Unable to load companies right now."
        ) from exc

    return PaginatedCompaniesSchema(items=items, total=total, page=page, page_size=page_size)


@router.get("/companies/export")
def export_companies(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    country: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    product: str | None = None,
    min_relevance: int | None = Query(default=None, ge=0, le=100),
    min_lead_score: int | None = Query(default=None, ge=0, le=100),
    has_email: bool | None = None,
    has_phone: bool | None = None,
    has_exported: bool | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export companies matching the given filters as CSV or Excel (Phase 8).

    Every exported company is stamped with `exported_at` so it can be told
    apart from fresh, not-yet-exported leads (`has_exported=false` filter).
    """
    try:
        companies = company_service.export_companies(
            db,
            country=country,
            region=region,
            industry=industry,
            product=product,
            min_relevance=min_relevance,
            min_lead_score=min_lead_score,
            has_email=has_email,
            has_phone=has_phone,
            has_exported=has_exported,
            search=search,
        )
        df = pd.DataFrame(company_service.to_export_rows(companies))
    except Exception as exc:
        logger.exception("Failed to export companies")
        raise HTTPException(
            status_code=500, detail="Unable to export companies right now."
        ) from exc

    buffer = io.BytesIO()
    if format == "xlsx":
        df.to_excel(buffer, index=False, sheet_name="Companies")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "petrolead-companies.xlsx"
    else:
        df.to_csv(buffer, index=False)
        media_type = "text/csv"
        filename = "petrolead-companies.csv"
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/companies/{company_id}", response_model=CompanyDetailSchema)
def get_company(company_id: str, db: Session = Depends(get_db)) -> CompanyDetailSchema:
    company = company_service.get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


@router.post("/discover", response_model=DiscoverResponseSchema)
async def discover_companies(
    payload: DiscoverRequestSchema, db: Session = Depends(get_db)
) -> DiscoverResponseSchema:
    """Run a discovery search. Results are a PREVIEW only — nothing is
    saved to your Companies list until you explicitly save a result via
    `POST /companies/save` (or `/save-bulk` for several at once)."""
    settings = get_settings()
    try:
        search_query, previews = await company_service.discover_preview(db, payload)
    except Exception as exc:
        logger.exception("Discovery job crashed unexpectedly")
        raise HTTPException(
            status_code=502, detail="Discovery failed unexpectedly. Please try again."
        ) from exc

    if search_query.status == SearchStatus.FAILED:
        raise HTTPException(
            status_code=502,
            detail=search_query.status_message or "Discovery failed. Please try again.",
        )

    return DiscoverResponseSchema(
        search_id=search_query.id,
        status=search_query.status.value,
        status_message=search_query.status_message,
        result_count=search_query.result_count,
        new_company_count=search_query.new_company_count,
        duplicate_count=search_query.duplicate_count,
        is_mock=settings.search_provider == "mock",
        companies=previews,
    )


@router.post("/discover-url", response_model=DiscoveredCompanyPreviewSchema)
async def discover_company_from_url(
    payload: DiscoverUrlRequestSchema, db: Session = Depends(get_db)
) -> DiscoveredCompanyPreviewSchema:
    """Paste-a-link quick lookup: fetch one URL and preview whatever public
    contact info is on it. This is a PREVIEW only — save it explicitly via
    `POST /companies/save` if you want to keep it. Works best for a
    company's own website — a raw social-media profile URL will usually
    come back with a clear 422 explaining why (those pages are typically
    login-gated)."""
    try:
        preview = await company_service.discover_from_url_preview(db, str(payload.url))
    except company_service.UrlLookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("URL lookup crashed unexpectedly for %s", payload.url)
        raise HTTPException(
            status_code=502, detail="Could not process this link right now. Please try again."
        ) from exc
    return preview


@router.post("/contacts/bulk-lookup", response_model=BulkContactLookupResponseSchema)
async def bulk_contact_lookup(
    payload: BulkContactLookupRequestSchema, db: Session = Depends(get_db)
) -> BulkContactLookupResponseSchema:
    """Look up several people at once — each item is either a LinkedIn
    profile URL or a plain name + company pair (same underlying lookup as
    `POST /discover-url`, just batched). Every item is independent: one
    failing never affects the others, and results come back in the same
    order as submitted. PREVIEW only — save individual results explicitly
    via `POST /companies/save` (or `/save-bulk`) if you want to keep them.
    """
    results = await company_service.bulk_contact_lookup_preview(db, payload.items)
    succeeded = sum(1 for r in results if r["success"])
    return BulkContactLookupResponseSchema(
        results=[
            BulkContactLookupResultSchema(
                input_url=str(r["item"].url) if r["item"].url else None,
                input_full_name=r["item"].full_name,
                input_company_name=r["item"].company_name,
                success=r["success"],
                error=r["error"],
                preview=r["preview"],
            )
            for r in results
        ],
        succeeded_count=succeeded,
        failed_count=len(results) - succeeded,
    )


@router.post("/companies/save", response_model=CompanyDetailSchema)
def save_company(
    payload: SaveCompanyRequestSchema, db: Session = Depends(get_db)
) -> CompanyDetailSchema:
    """Save one previewed company (from `/discover` or `/discover-url`) to
    your Companies list. Safe to call on a company that's already saved —
    it merges into the existing record instead of duplicating it."""
    try:
        return company_service.save_candidate(db, payload)
    except company_service.CompanySaveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to save company %r", payload.company_name)
        raise HTTPException(
            status_code=500, detail="Could not save this company. Please try again."
        ) from exc


@router.post("/companies/save-bulk", response_model=SaveCompaniesBulkResponseSchema)
def save_companies_bulk(
    payload: SaveCompaniesBulkRequestSchema, db: Session = Depends(get_db)
) -> SaveCompaniesBulkResponseSchema:
    """Save several previewed companies at once ("Save All" on a results page)."""
    try:
        saved, new_count, duplicate_count = company_service.save_candidates_bulk(
            db, payload.companies
        )
    except Exception as exc:
        logger.exception("Bulk save crashed unexpectedly")
        raise HTTPException(
            status_code=500, detail="Could not save these companies. Please try again."
        ) from exc
    return SaveCompaniesBulkResponseSchema(
        saved=saved, new_count=new_count, duplicate_count=duplicate_count
    )


@router.get("/searches")
def get_searches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    try:
        items, total = company_service.list_searches(db, page=page, page_size=page_size)
    except Exception as exc:
        logger.exception("Failed to list searches")
        raise HTTPException(
            status_code=500, detail="Unable to load search history right now."
        ) from exc

    return {
        "items": [SearchQuerySchema.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }
