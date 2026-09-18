"""Pydantic request/response schemas for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_LIMITS = {10, 25, 50, 100}
MAX_BULK_LOOKUP_ITEMS = 25
MAX_VERIFY_EMAILS = 500


class DiscoverUrlRequestSchema(BaseModel):
    """Body for POST /api/discover-url — the "paste a link" quick lookup."""

    url: AnyHttpUrl


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
    include_social_search: bool = Field(default=False)
    include_b2b_directories: bool = Field(default=False)

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


class PreviewSocialProfileSchema(BaseModel):
    platform: str
    url: str


class PreviewEmailSchema(BaseModel):
    email: str
    is_valid: bool | None = None


class PreviewPhoneSchema(BaseModel):
    phone: str
    is_valid: bool = False


class DiscoveredCompanyPreviewSchema(BaseModel):
    """A discovered-but-not-yet-saved company — the shape returned by
    `/discover` and `/discover-url`. Nothing with this shape exists in the
    database until the client echoes it back to `/companies/save`."""

    # Null when a person was found without an identifiable employer. The
    # contact is still returned, but `/companies/save` requires a name, so
    # the client must collect one before such a preview can be saved.
    company_name: str | None = None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    region: str | None = None
    industry: str | None = None
    description: str | None = None
    activities: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source: str = "unknown"
    source_url: str | None = None
    is_mock: bool = False
    contact_page_url: str | None = None
    social_profiles: list[PreviewSocialProfileSchema] = Field(default_factory=list)
    emails: list[PreviewEmailSchema] = Field(default_factory=list)
    phones: list[PreviewPhoneSchema] = Field(default_factory=list)
    # Only set by the personal-profile search-snippet fallback ("paste a
    # link" with a linkedin.com/in/... URL) — see `contact_person_name` on
    # `DiscoveredCompany` for how this gets populated.
    contact_person_name: str | None = None
    contact_person_title: str | None = None
    relevance_score: int
    lead_score: int
    already_saved: bool
    existing_company_id: str | None = None


class BulkContactLookupItemSchema(BaseModel):
    """One row of a bulk lookup — either a LinkedIn profile URL, or a name
    + company pair. Exactly one form must be given, not both."""

    url: AnyHttpUrl | None = None
    full_name: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _exactly_one_form(self) -> BulkContactLookupItemSchema:
        has_url = self.url is not None
        has_name_and_company = bool(self.full_name and self.full_name.strip()) and bool(
            self.company_name and self.company_name.strip()
        )
        if has_url == has_name_and_company:
            raise ValueError(
                "Provide either a url, or both full_name and company_name — not both forms."
            )
        return self


class BulkContactLookupRequestSchema(BaseModel):
    """Body for POST /api/contacts/bulk-lookup."""

    items: list[BulkContactLookupItemSchema] = Field(min_length=1, max_length=MAX_BULK_LOOKUP_ITEMS)


class BulkContactLookupResultSchema(BaseModel):
    input_url: str | None = None
    input_full_name: str | None = None
    input_company_name: str | None = None
    success: bool
    error: str | None = None
    preview: DiscoveredCompanyPreviewSchema | None = None


class BulkContactLookupResponseSchema(BaseModel):
    results: list[BulkContactLookupResultSchema]
    succeeded_count: int
    failed_count: int


class SaveCompanyRequestSchema(BaseModel):
    """Body for POST /api/companies/save — a client echoing back a preview
    (from `/discover` or `/discover-url`) it wants persisted."""

    company_name: str = Field(min_length=1, max_length=500)
    website: str | None = None
    country: str | None = None
    city: str | None = None
    region: str | None = None
    industry: str | None = None
    description: str | None = None
    activities: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source: str = "manual"
    source_url: str | None = None
    is_mock: bool = False
    contact_page_url: str | None = None
    social_profiles: list[PreviewSocialProfileSchema] = Field(default_factory=list)
    emails: list[PreviewEmailSchema] = Field(default_factory=list)
    phones: list[PreviewPhoneSchema] = Field(default_factory=list)
    contact_person_name: str | None = None
    contact_person_title: str | None = None


class SaveCompaniesBulkRequestSchema(BaseModel):
    """Body for POST /api/companies/save-bulk — "Save All" on a results page."""

    companies: list[SaveCompanyRequestSchema] = Field(default_factory=list, max_length=200)


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
    exported_at: datetime | None = None

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
    contact_person_name: str | None
    contact_person_title: str | None
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


class ExtractedEmailSchema(BaseModel):
    email: str
    is_valid: bool | None
    discovered_at: datetime
    exported_at: datetime | None
    company_id: str
    company_name: str
    company_website: str | None
    company_country: str | None
    company_industry: str | None


class PaginatedEmailsSchema(BaseModel):
    items: list[ExtractedEmailSchema]
    total: int
    page: int
    page_size: int


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
    companies: list[DiscoveredCompanyPreviewSchema]


class SaveCompaniesBulkResponseSchema(BaseModel):
    """`results[i]` is the outcome for `request.companies[i]` — `None` if
    that one failed to save. Positional, not matched by name/website,
    since a merge keeps the existing saved company's name rather than the
    incoming candidate's — see `company_service.save_candidates_bulk`."""

    results: list[CompanySummarySchema | None]
    new_count: int
    duplicate_count: int


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


class VerifyEmailsRequestSchema(BaseModel):
    """Body for POST /api/emails/verify — the Email Verifier."""

    emails: list[str] = Field(min_length=1, max_length=MAX_VERIFY_EMAILS)


class VerifiedEmailSchema(BaseModel):
    """One graded address.

    `status` answers "will this bounce?" and `reason` says why. Only
    `deliverable` is safe to send to — `risky` covers catch-all domains,
    unconfirmed shared role inboxes and (without a verification provider
    configured) addresses where only the domain could be checked.

    A shared inbox a provider has confirmed is `deliverable` with reason
    `role_confirmed`: it will not bounce, which is what this grades.
    Whether it's a good address to cold-mail is a separate question, and
    the reason is what answers it.
    """

    email: str
    status: Literal["deliverable", "undeliverable", "risky", "unknown"]
    reason: Literal[
        "mailbox_confirmed",
        "invalid_format",
        "no_mail_server",
        "disposable_domain",
        "typo_suspected",
        "mailbox_not_found",
        "catch_all",
        "role_account",
        "role_confirmed",
        "domain_only",
        "dns_error",
        "provider_error",
    ]
    syntax_valid: bool
    # None when the format was invalid (no lookup ran) or the DNS check failed.
    domain_accepts_mail: bool | None


class VerifyEmailsResponseSchema(BaseModel):
    results: list[VerifiedEmailSchema]
    deliverable_count: int
    undeliverable_count: int
    risky_count: int
    unknown_count: int
    # False when no verification provider is configured, so nothing in this
    # batch could be confirmed at the mailbox level — the UI says so rather
    # than letting "risky" read as a fault in the addresses.
    mailbox_checks_available: bool


class ErrorResponseSchema(BaseModel):
    detail: str
