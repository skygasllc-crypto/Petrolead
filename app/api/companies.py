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
    CompanyDetailSchema,
    DiscoverRequestSchema,
    DiscoverResponseSchema,
    PaginatedCompaniesSchema,
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
    search: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export companies matching the given filters as CSV or Excel (Phase 8)."""
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
    settings = get_settings()
    try:
        search_query = await company_service.run_discovery(db, payload)
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

    companies = getattr(search_query, "result_companies", [])
    return DiscoverResponseSchema(
        search_id=search_query.id,
        status=search_query.status.value,
        status_message=search_query.status_message,
        result_count=search_query.result_count,
        new_company_count=search_query.new_company_count,
        duplicate_count=search_query.duplicate_count,
        is_mock=settings.search_provider == "mock",
        companies=companies,
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
