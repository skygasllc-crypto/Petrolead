"""Shared data structures for the discovery subsystem.

`DiscoveredCompany` is the common contract every source connector
returns, regardless of where the data came from (web search, a B2B
directory, a company website, a future social/API connector). The
database layer and frontend only ever need to understand this one
shape — adding a new source means writing a new connector, not
touching the rest of the app.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiscoveryRequest:
    """Parameters for a company discovery job."""

    region: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    activity: str | None = None
    # What kind of counterparty to look for — "Suppliers", "Traders" and so
    # on (see `search.ROLE_PHRASE_SUFFIXES`). None means any, and adds no
    # role wording to the queries.
    role: str | None = None
    products: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    limit: int = 25

    # Phase 5/6 (partial): also run search queries targeted at known
    # social-platform company pages / B2B trade-directory listings via
    # `site:` operators. Both opt-in — they add extra search-provider
    # calls, which cost quota/money on real providers. Neither ever
    # fetches the third-party page's own content; see `discovery/search.py`
    # and `discovery/sources.py` for why.
    include_social_search: bool = False
    include_b2b_directories: bool = False


@dataclass
class DiscoveredCompany:
    """A single company as returned by any source connector, pre-persistence."""

    # None only for a person found without an identifiable employer (the
    # LinkedIn profile-snippet fallback): the contact is still worth
    # showing, but there's no company to attach them to until the user
    # names one, so such a candidate is preview-only and can't be saved —
    # `companies.company_name` is NOT NULL.
    company_name: str | None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    region: str | None = None
    industry: str | None = None
    description: str | None = None
    activities: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source: str = "unknown"
    source_url: str | None = None
    is_mock: bool = False

    # --- Phase 2: business contact discovery ---
    # Populated only from links a company published on its own public
    # website (a "Contact" page link, a linked LinkedIn/Facebook/etc.
    # profile).
    contact_page_url: str | None = None
    social_profiles: list[dict[str, str]] = field(default_factory=list)

    # Populated only via the personal-profile search-snippet fallback (see
    # `company_service._preview_from_profile_snippet`) — never by fetching
    # a login-gated profile page directly.
    contact_person_name: str | None = None
    contact_person_title: str | None = None

    # --- Phase 3/4: business email & phone extraction ---
    # Each entry: {"email"|"phone": str, "is_valid": bool | None}.
    emails: list[dict[str, object]] = field(default_factory=list)
    phones: list[dict[str, object]] = field(default_factory=list)
