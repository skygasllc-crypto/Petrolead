"""Pydantic request/response schemas for the public API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_LIMITS = {10, 25, 50, 100}


class DiscoverRequestSchema(BaseModel):
    """Body for POST /api/discover."""

    region: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, max_length=150)
    industry: str | None = Field(default=None, max_length=150)
    activity: str | None = Field(default=None, max_length=150)
    products: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    limit: int = Field(default=25)

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value not in ALLOWED_LIMITS:
            raise ValueError(f"limit must be one of {sorted(ALLOWED_LIMITS)}")
        return value

    @field_validator("keywords", "products")
    @classmethod
    def strip_blank_entries(cls, value: list[str]) -> list[str]:
        return [v.strip() for v in value if v and v.strip()]

    @field_validator("region", "country", "city", "industry", "activity")
    @classmethod
    def strip_str(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class CompanySourceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    source_url: str | None
    raw_company_name: str | None
    match_confidence: float | None
    discovered_at: datetime


class CompanySummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_name: str
    country: str | None
    city: str | None
    region: str | None
    industry: str | None
    products: list[str]
    website: str | None
    source: str | None
    relevance_score: int
    lead_score: int | None = None
    discovered_at: datetime

    @field_validator("lead_score", mode="before")
    @classmethod
    def _extract_lead_score(cls, value: object) -> int | None:
        # `Company.lead_score` is a one-to-one relationship to a `LeadScore`
        # row (or None); pull out the plain numeric score for the API.
        if value is None or isinstance(value, int):
            return value
        return getattr(value, "score", None)


class CompanyContactSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_page_url: str | None
    discovered_at: datetime


class SocialProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    url: str
    discovered_at: datetime


class CompanyEmailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    is_valid: bool | None
    discovered_at: datetime


class CompanyPhoneSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phone: str
    is_valid: bool
    discovered_at: datetime


class LeadScoreBreakdownSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    relevance_component: int
    contact_completeness_component: int
    verified_email_component: int
    verified_phone_component: int
    computed_at: datetime


class CompanyDetailSchema(CompanySummarySchema):
    normalized_name: str
    description: str | None
    activities: list[str]
    keywords: list[str]
    domain: str | None
    source_url: str | None
    updated_at: datetime
    sources: list[CompanySourceSchema] = Field(default_factory=list)
    contact: CompanyContactSchema | None = None
    social_profiles: list[SocialProfileSchema] = Field(default_factory=list)
    emails: list[CompanyEmailSchema] = Field(default_factory=list)
    phones: list[CompanyPhoneSchema] = Field(default_factory=list)
    lead_score_breakdown: LeadScoreBreakdownSchema | None = Field(
        default=None, validation_alias="lead_score"
    )


class PaginatedCompaniesSchema(BaseModel):
    items: list[CompanySummarySchema]
    total: int
    page: int
    page_size: int


class DiscoverResponseSchema(BaseModel):
    search_id: str
    status: str
    status_message: str | None
    result_count: int
    new_company_count: int
    duplicate_count: int
    is_mock: bool
    companies: list[CompanySummarySchema]


class SearchQuerySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    region: str | None
    country: str | None
    city: str | None
    industry: str | None
    activity: str | None
    products: list[str]
    keywords: list[str]
    result_limit: int
    status: str
    status_message: str | None
    result_count: int
    new_company_count: int
    duplicate_count: int
    created_at: datetime
    completed_at: datetime | None
    saved_search_id: str | None = None


ALLOWED_FREQUENCIES = {"daily", "weekly"}


class SavedSearchCreateSchema(BaseModel):
    """Body for POST /api/saved-searches (Phase 10)."""

    name: str = Field(min_length=1, max_length=200)
    region: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, max_length=150)
    industry: str | None = Field(default=None, max_length=150)
    activity: str | None = Field(default=None, max_length=150)
    products: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    limit: int = Field(default=25)
    frequency: str = Field(default="daily")

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value not in ALLOWED_LIMITS:
            raise ValueError(f"limit must be one of {sorted(ALLOWED_LIMITS)}")
        return value

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str) -> str:
        if value not in ALLOWED_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(ALLOWED_FREQUENCIES)}")
        return value

    @field_validator("keywords", "products")
    @classmethod
    def strip_blank_entries(cls, value: list[str]) -> list[str]:
        return [v.strip() for v in value if v and v.strip()]

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class SavedSearchSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    region: str | None
    country: str | None
    city: str | None
    industry: str | None
    activity: str | None
    products: list[str]
    keywords: list[str]
    result_limit: int
    frequency: str
    is_active: bool
    created_at: datetime
    last_run_at: datetime | None
    next_run_at: datetime | None


class ErrorResponseSchema(BaseModel):
    detail: str
