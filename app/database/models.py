"""SQLAlchemy ORM models.

Phase 1 covers `Company`, `CompanySource` (provenance / dedup trail) and
`SearchQuery` (discovery job history). Phase 2 adds `CompanyContact` and
`SocialProfile`. Phase 3/4 add `CompanyEmail`/`CompanyPhone`. Phase 7 adds
`LeadScore`. The schema stays normalized so later phases (verification
results, saved/scheduled searches, ...) can add new tables with a foreign
key onto `companies.id`, without touching what's already here.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
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


class User(Base):
    """An account with access to the app.

    Each account's saved companies, search history and scheduled searches
    are private to it — see the `owner_id` columns on `Company`,
    `SearchQuery` and `SavedSearch`.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Grants access to the /admin/users endpoints (view all accounts,
    # block/unblock). Synced from `ADMIN_EMAILS` on every register/login —
    # see `app.api.auth`.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # The account's paid plan and credit balance, or None for no plan.
    subscription: Mapped[Subscription | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id!r} email={self.email!r}>"


class Subscription(Base):
    """A user's plan, email-credit balance and daily usage counter.

    Credits are granted per monthly period and roll over;
    renewal happens lazily the next time the account is used — see
    `app.services.billing_service`. Plan limits live in `app.services.plans`.
    """

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    credits_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    renews_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Company discovery searches run on `discovery_day` (a UTC date, ISO
    # format); the counter starts again when the day changes.
    discovery_day: Mapped[str | None] = mapped_column(String(10))
    discovery_searches_today: Mapped[int] = mapped_column(Integer, default=0)

    # End of the period the customer has paid for. The plan stops working
    # (and stops receiving monthly credits) once it passes. None for plans
    # an admin assigned without a payment — those don't expire.
    paid_until: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="subscription")


class PaymentOrder(Base):
    """A crypto payment for a plan, checked and confirmed by an admin.

    The customer sends coins to the receiving address shown, then marks the
    order paid with the transaction ID. An admin checks that transaction on
    a block explorer and confirms it — activating the plan — or rejects it.
    No payment processor, wallet software or private keys are involved; see
    `app.services.payment_service`.
    """

    __tablename__ = "payment_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_payment_orders_user_id_users"),
        index=True,
        nullable=False,
    )

    # Short code generated for the customer (e.g. PL-7K3D9A2M). It identifies
    # the order in the app — BTC and TRC-20 transfers carry no memo, so it
    # never travels with the coins.
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    credits_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_period: Mapped[str] = mapped_column(String(10), nullable=False)  # monthly | yearly
    amount_usd_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    currency: Mapped[str] = mapped_column(String(20), nullable=False)  # BTC | USDT_TRC20 | TRX
    pay_address: Mapped[str] = mapped_column(String(120), nullable=False)
    # The exact amount the customer was asked to send, as a decimal string.
    amount_crypto: Mapped[str] = mapped_column(String(40), nullable=False)
    # US dollars per coin used for the quote; None for USDT (priced 1:1).
    usd_rate: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    # Optional: the customer can add the blockchain transaction ID, or an
    # admin can record the one they found while checking the payment.
    tx_hash: Mapped[str | None] = mapped_column(String(100), unique=True)
    admin_note: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    # When the price quote lapses if the order hasn't been marked paid.
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_payment_orders_reviewed_by_id_users")
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class CreditTransaction(Base):
    """Audit trail of every credit change: plan grants, monthly renewals,
    admin adjustments and credits spent on found emails."""

    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500))
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Company(Base):
    """A discovered, deduplicated petroleum-industry company record."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # The account this company belongs to. Each account's companies are
    # private to it, including for duplicate detection.
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", name="fk_companies_owner_id_users"), index=True, nullable=False
    )

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
    # Set when this company is included in a CSV/Excel export (Phase 8) —
    # lets a user tell "already sent to my CRM/outreach list" apart from
    # fresh leads. Never cleared automatically; re-exporting just bumps it.
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    sources: Mapped[list[CompanySource]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    contact: Mapped[CompanyContact | None] = relationship(
        back_populates="company", cascade="all, delete-orphan", uselist=False
    )
    social_profiles: Mapped[list[SocialProfile]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    emails: Mapped[list[CompanyEmail]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    phones: Mapped[list[CompanyPhone]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    lead_score: Mapped[LeadScore | None] = relationship(
        back_populates="company", cascade="all, delete-orphan", uselist=False
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


class CompanyContact(Base):
    """General business-contact info discovered on a company's own website.

    One row per company. Deliberately limited to what a company itself
    published in its page markup (a "Contact" page link) — never an email
    address or phone number, which are extracted (with validation) in
    Phase 3/4 instead.
    """

    __tablename__ = "company_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id"), unique=True, index=True
    )

    contact_page_url: Mapped[str | None] = mapped_column(String(1000))

    # A named contact at the company, when one was found — currently only
    # sourced from a public search-engine snippet for a personal LinkedIn
    # profile URL pasted into "paste a link" (the profile page itself is
    # login-gated and never fetched directly; see
    # `app.services.company_service._preview_from_profile_snippet`).
    contact_person_name: Mapped[str | None] = mapped_column(String(200))
    contact_person_title: Mapped[str | None] = mapped_column(String(200))

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    company: Mapped[Company] = relationship(back_populates="contact")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CompanyContact company_id={self.company_id!r}>"


class SocialProfile(Base):
    """A social-platform profile link a company published on its own website.

    Populated only from a hyperlink literally present in the company's page
    markup — never by guessing a handle or visiting a login-gated profile.
    """

    __tablename__ = "social_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="social_profiles")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SocialProfile company_id={self.company_id!r} platform={self.platform!r}>"


class CompanyEmail(Base):
    """A business email address found on a company's own public pages (Phase 3).

    `is_valid` reflects a live MX-record check on the domain at discovery
    time — not proof a mailbox exists, and never established by sending
    mail. `None` means the check couldn't be completed (not evidence of
    invalidity), matching `app.discovery.emails.validate_email_domain`.
    """

    __tablename__ = "company_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    is_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Set when this email is included in a CSV/Excel export from the
    # Emails page. Never cleared automatically; re-exporting bumps it.
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    company: Mapped[Company] = relationship(back_populates="emails")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CompanyEmail company_id={self.company_id!r} email={self.email!r}>"


class CompanyPhone(Base):
    """A business phone number found on a company's own public pages (Phase 4).

    `is_valid` reflects purely structural validation (libphonenumber) — is
    this a plausible, dialable number for its country — never a placed
    call.
    """

    __tablename__ = "company_phones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)

    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="phones")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CompanyPhone company_id={self.company_id!r} phone={self.phone!r}>"


class LeadScore(Base):
    """Composite lead-quality score for a company (Phase 7).

    A simple, transparent weighted formula over relevance + how complete
    and verified the company's contact footprint is — deliberately not a
    black box, and recomputed every time new information is discovered.
    """

    __tablename__ = "lead_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True, index=True)

    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    relevance_component: Mapped[int] = mapped_column(Integer, default=0)
    contact_completeness_component: Mapped[int] = mapped_column(Integer, default=0)
    verified_email_component: Mapped[int] = mapped_column(Integer, default=0)
    verified_phone_component: Mapped[int] = mapped_column(Integer, default=0)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    company: Mapped[Company] = relationship(back_populates="lead_score")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LeadScore company_id={self.company_id!r} score={self.score!r}>"


class SearchQuery(Base):
    """A discovery job submitted by a user — the search history log."""

    __tablename__ = "search_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # The account that ran this search.
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", name="fk_search_queries_owner_id_users"),
        index=True,
        nullable=False,
    )

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

    # Set only when this run was triggered by a schedule rather than a user
    # clicking "Discover Companies" (Phase 10).
    saved_search_id: Mapped[str | None] = mapped_column(
        ForeignKey("saved_searches.id"), index=True, nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SearchQuery id={self.id!r} status={self.status!r}>"


class SavedSearch(Base):
    """A discovery search saved to run automatically on a schedule (Phase 10).

    Execution itself lives in `app.worker` (Celery beat, checking
    `next_run_at`) so the API layer only ever manages the schedule, never
    blocks a request on running it.
    """

    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # The account this schedule belongs to; its runs save companies for that account.
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", name="fk_saved_searches_owner_id_users"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(150))
    city: Mapped[str | None] = mapped_column(String(150))
    industry: Mapped[str | None] = mapped_column(String(150))
    activity: Mapped[str | None] = mapped_column(String(150))
    products: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    result_limit: Mapped[int] = mapped_column(Integer, default=25)

    frequency: Mapped[str] = mapped_column(String(20), default="daily")  # "daily" | "weekly"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SavedSearch id={self.id!r} name={self.name!r}>"
