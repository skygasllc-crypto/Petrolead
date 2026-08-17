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
    products: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    limit: int = 25


@dataclass
class DiscoveredCompany:
    """A single company as returned by any source connector, pre-persistence."""

    company_name: str
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
