"""A dedicated view over every extracted business email, across all companies.

`Company.emails` already exists per-company on the Company Profile page;
this module is the flat, cross-company "folder" of every `CompanyEmail`
row — filterable and exportable on its own, independent of which company
each one belongs to.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from app.database.models import Company, CompanyEmail, utcnow

MAX_EMAIL_EXPORT_ROWS = 5000


def _row_to_dict(email: CompanyEmail) -> dict:
    return {
        "email": email.email,
        "is_valid": email.is_valid,
        "discovered_at": email.discovered_at,
        "exported_at": email.exported_at,
        "company_id": email.company_id,
        "company_name": email.company.company_name,
        "company_website": email.company.website,
        "company_country": email.company.country,
        "company_industry": email.company.industry,
    }


def _filtered_emails_stmt(
    *,
    search: str | None = None,
    is_valid: bool | None = None,
    country: str | None = None,
    industry: str | None = None,
    has_exported: bool | None = None,
):
    stmt = (
        select(CompanyEmail)
        .join(Company, CompanyEmail.company_id == Company.id)
        .options(contains_eager(CompanyEmail.company))
    )
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(func.lower(CompanyEmail.email).like(like))
    if is_valid is True:
        stmt = stmt.where(CompanyEmail.is_valid.is_(True))
    elif is_valid is False:
        stmt = stmt.where(CompanyEmail.is_valid.is_(False))
    if country:
        stmt = stmt.where(Company.country == country)
    if industry:
        stmt = stmt.where(Company.industry == industry)
    if has_exported is True:
        stmt = stmt.where(CompanyEmail.exported_at.isnot(None))
    elif has_exported is False:
        stmt = stmt.where(CompanyEmail.exported_at.is_(None))
    return stmt


def list_emails(
    db: Session,
    *,
    search: str | None = None,
    is_valid: bool | None = None,
    country: str | None = None,
    industry: str | None = None,
    has_exported: bool | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    stmt = _filtered_emails_stmt(
        search=search,
        is_valid=is_valid,
        country=country,
        industry=industry,
        has_exported=has_exported,
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = (
        stmt.order_by(CompanyEmail.discovered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_row_to_dict(e) for e in db.execute(stmt).scalars().all()]
    return items, total


def export_emails(
    db: Session,
    *,
    search: str | None = None,
    is_valid: bool | None = None,
    country: str | None = None,
    industry: str | None = None,
    has_exported: bool | None = None,
    mark_exported: bool = True,
) -> list[dict]:
    stmt = _filtered_emails_stmt(
        search=search,
        is_valid=is_valid,
        country=country,
        industry=industry,
        has_exported=has_exported,
    )
    stmt = stmt.order_by(CompanyEmail.discovered_at.desc()).limit(MAX_EMAIL_EXPORT_ROWS)
    rows = list(db.execute(stmt).scalars().all())

    if mark_exported and rows:
        now = utcnow()
        for row in rows:
            row.exported_at = now
        db.commit()

    return [_row_to_dict(e) for e in rows]


def _verification_label(is_valid: bool | None) -> str:
    if is_valid is True:
        return "Yes"
    if is_valid is False:
        return "Unverified"
    return "Pending"


def to_export_rows(emails: list[dict]) -> list[dict]:
    return [
        {
            "Email": e["email"],
            "Verified": _verification_label(e["is_valid"]),
            "Company Name": e["company_name"],
            "Company Website": e["company_website"] or "",
            "Country": e["company_country"] or "",
            "Industry": e["company_industry"] or "",
            "Discovered Date": e["discovered_at"].isoformat(),
            "Exported Date": e["exported_at"].isoformat() if e["exported_at"] else "",
        }
        for e in emails
    ]
