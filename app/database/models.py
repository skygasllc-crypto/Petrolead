"""SQLAlchemy ORM models.

Phase 1 focuses on `Company`, `CompanySource` (provenance / dedup trail)
and `SearchQuery` (discovery job history). The schema is intentionally
normalized so that later phases can add `contacts`, `emails`,
`phone_numbers`, `social_profiles`, `lead_scores`, and
`verification_results` as new tables with a foreign key onto
`companies.id`, without touching this table.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SearchStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Company(Base):
    """A discovered, deduplicated petroleum-industry company record."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # --- Identity ---
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    # --- Location ---
    country: Mapped[str | None] = mapped_column(String(150), index=True)
    city: Mapped[str | None] = mapped_column(String(150), index=True)
    region: Mapped[str | None] = mapped_column(String(100), index=True)

    # --- Web presence ---
    website: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str | None] = mapped_column(String(300), index=True)

    # --- Classification ---
    industry: Mapped[str | None] = mapped_column(String(150), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    activities: Mapped[list[str]] = mapped_column(JSON, default=list)
    products: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)

    # --- Discovery provenance (first-seen source; full trail in CompanySource) ---
    source: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1000))

    # --- Relevance ---
    relevance_score: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # --- Timestamps ---
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    sources: Mapped[list[CompanySource]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company id={self.id!r} name={self.company_name!r}>"


class CompanySource(Base):
    """One discovery event: which source found this company, and what it saw.

    Kept separate from `Company` so that deduplication can merge multiple
    discoveries into a single company record without losing provenance —
    important for trust/verification in later phases.
    """

    __tablename__ = "company_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    raw_company_name: Mapped[str | None] = mapped_column(String(500))
    match_confidence: Mapped[float | None] = mapped_column(default=1.0)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="sources")


class SearchQuery(Base):
    """A discovery job submitted by a user — the search history log."""

    __tablename__ = "search_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str | None] = mapped_column(String(150))
    industry: Mapped[str | None] = mapped_column(String(150))
    activity: Mapped[str | None] = mapped_column(String(150))
    products: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    result_limit: Mapped[int] = mapped_column(Integer, default=25)

    status: Mapped[SearchStatus] = mapped_column(
        Enum(SearchStatus, native_enum=False), default=SearchStatus.PENDING, index=True
    )
    status_message: Mapped[str | None] = mapped_column(String(500))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    new_company_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SearchQuery id={self.id!r} status={self.status!r}>"
