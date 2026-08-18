"""Turns raw search results / web pages into `DiscoveredCompany` candidates.

Two extraction paths:

* `company_from_search_result` — cheap, works off the search snippet alone
  (title/url/snippet). Always available.
* `enrich_from_website` — optionally fetches the company's own site and
  pulls a better description out of its meta tags / visible text. Uses
  httpx + BeautifulSoup against publicly reachable pages only; never
  bypasses logins, CAPTCHAs, or anti-bot protections, and fails soft
  (timeouts / malformed HTML never crash the discovery job).
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.discovery.contacts import find_contact_page, find_social_profiles
from app.discovery.normalizer import extract_domain
from app.discovery.search import SearchResultItem
from app.discovery.types import DiscoveredCompany, DiscoveryRequest

logger = logging.getLogger("petrolead.discovery.extractor")

# Titles from search engines often carry a trailing "| Site Name" or
# "- Site Name" suffix, and directory listings a leading "Company: " label.
_TITLE_TRIM_RE = re.compile(r"\s*[\|\-–—]\s*[^|\-–—]{1,60}$")


def company_from_search_result(
    result: SearchResultItem,
    request: DiscoveryRequest,
    *,
    source: str,
    is_mock: bool = False,
) -> DiscoveredCompany:
    """Build a first-pass `DiscoveredCompany` from a search result alone."""
    company_name = _clean_title(result.title) or result.url
    website = result.url or None

    contact_page_url: str | None = None
    social_profiles: list[dict[str, str]] = []
    if is_mock and website:
        # Synthetic, clearly-labeled contact/social data for UI testing only
        # — derived deterministically from the mock domain, never presented
        # as real. Mirrors the "[MOCK]" labeling already applied to the name.
        contact_page_url = f"{website.rstrip('/')}/contact"
        slug = extract_domain(website) or "example"
        social_profiles = [
            {"platform": "linkedin", "url": f"https://linkedin.com/company/{slug}"},
            {"platform": "facebook", "url": f"https://facebook.com/{slug}"},
        ]

    return DiscoveredCompany(
        company_name=company_name,
        website=website,
        country=request.country,
        city=request.city,
        region=request.region,
        industry=request.industry,
        description=result.snippet or None,
        activities=[request.activity] if request.activity else [],
        products=list(request.products),
        keywords=list(request.keywords),
        source=source,
        source_url=result.url or None,
        is_mock=is_mock,
        contact_page_url=contact_page_url,
        social_profiles=social_profiles,
    )


def _clean_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return ""
    trimmed = _TITLE_TRIM_RE.sub("", title).strip()
    # Only trust the trim if it didn't gut the whole title.
    return trimmed if len(trimmed) >= max(3, len(title) * 0.4) else title


async def enrich_from_website(
    company: DiscoveredCompany, *, settings: Settings | None = None
) -> DiscoveredCompany:
    """Best-effort enrichment by fetching the company's public homepage.

    Never raises: any network/parse failure just returns `company` unchanged
    (logged, not surfaced as a hard error — a single unreachable site should
    not abort an entire discovery job).
    """
    if company.is_mock or not company.website:
        return company

    settings = settings or get_settings()
    headers = {"User-Agent": settings.http_user_agent}

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, follow_redirects=True, headers=headers
        ) as client:
            response = await client.get(company.website)
            response.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.warning("enrich_from_website: could not fetch %s (%s)", company.website, exc)
        return company

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type:
        return company

    try:
        soup = BeautifulSoup(response.text, "lxml")
    except Exception as exc:  # malformed markup shouldn't break the pipeline
        logger.warning("enrich_from_website: could not parse %s (%s)", company.website, exc)
        return company

    meta_description = _meta_description(soup)
    if meta_description and (
        not company.description or len(meta_description) > len(company.description)
    ):
        company.description = meta_description

    company.contact_page_url = find_contact_page(soup, str(response.url))
    company.social_profiles = find_social_profiles(soup, str(response.url))

    return company


def _meta_description(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if tag and tag.get("content"):
        return tag["content"].strip()[:1000]

    paragraph = soup.find("p")
    if paragraph and paragraph.get_text(strip=True):
        return paragraph.get_text(strip=True)[:1000]

    return None
