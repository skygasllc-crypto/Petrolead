"""Turns raw search results / web pages into `DiscoveredCompany` candidates.

Two extraction paths:

* `company_from_search_result` — cheap, works off the search snippet alone
  (title/url/snippet). Always available.
* `enrich_from_website` — fetches the company's own homepage (and, if
  found, its Contact page) and pulls a better description, contact page
  link, social-profile links, and business emails/phones out of them.
  Uses httpx + BeautifulSoup against publicly reachable pages only; never
  bypasses logins, CAPTCHAs, or anti-bot protections, and fails soft
  (timeouts / malformed HTML never crash the discovery job).
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.core.net_guard import MAX_REDIRECTS, BlockedURLError, block_internal_requests
from app.discovery.contacts import find_contact_page, find_social_profiles
from app.discovery.emails import MAX_EMAILS_PER_COMPANY, extract_emails, validate_email_domain
from app.discovery.normalizer import extract_domain
from app.discovery.phones import (
    MAX_PHONES_PER_COMPANY,
    extract_phone_text_candidates,
    extract_tel_link_candidates,
    validate_phone,
)
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
    treat_url_as_website: bool = True,
) -> DiscoveredCompany:
    """Build a first-pass `DiscoveredCompany` from a search result alone.

    `treat_url_as_website=False` is used for B2B-directory-sourced results
    (Phase 6): the result URL is a third party's own listing page, not the
    company's site, so it's kept only as `source_url` (provenance) and
    never as `website` — which matters because `enrich_from_website` would
    otherwise fetch it, i.e. scrape the directory's page. See
    `discovery/search.py` for the full rationale.
    """
    company_name = _clean_title(result.title) or result.url
    website = result.url if (treat_url_as_website and result.url) else None

    contact_page_url: str | None = None
    social_profiles: list[dict[str, str]] = []
    emails: list[dict[str, object]] = []
    phones: list[dict[str, object]] = []
    if is_mock and website:
        # Synthetic, clearly-labeled contact/social/email/phone data for UI
        # testing only — deterministically derived from the mock domain,
        # never presented as real. Mirrors the "[MOCK]" label on the name.
        contact_page_url = f"{website.rstrip('/')}/contact"
        slug = extract_domain(website) or "example"
        social_profiles = [
            {"platform": "linkedin", "url": f"https://linkedin.com/company/{slug}"},
            {"platform": "facebook", "url": f"https://facebook.com/{slug}"},
        ]
        emails = [{"email": f"info@{slug}", "is_valid": None}]
        phones = [{"phone": "+000 000 0000", "is_valid": False}]

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
        emails=emails,
        phones=phones,
    )


def _clean_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return ""
    trimmed = _TITLE_TRIM_RE.sub("", title).strip()
    # Only trust the trim if it didn't gut the whole title.
    return trimmed if len(trimmed) >= max(3, len(title) * 0.4) else title


async def _fetch_page(
    client: httpx.AsyncClient, url: str
) -> tuple[BeautifulSoup, str, str] | None:
    """Fetch and parse one page. Returns (soup, visible_text, final_url) or None."""
    try:
        response = await client.get(url)
        response.raise_for_status()
    except BlockedURLError as exc:
        # Someone pointed us at a private address (see app.core.net_guard).
        logger.warning("extractor: refused to fetch %s (%s)", url, exc)
        return None
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.warning("extractor: could not fetch %s (%s)", url, exc)
        return None

    if "html" not in response.headers.get("content-type", ""):
        return None

    try:
        soup = BeautifulSoup(response.text, "lxml")
    except Exception as exc:  # malformed markup shouldn't break the pipeline
        logger.warning("extractor: could not parse %s (%s)", url, exc)
        return None

    return soup, soup.get_text(" ", strip=True), str(response.url)


async def enrich_from_website(
    company: DiscoveredCompany, *, settings: Settings | None = None
) -> DiscoveredCompany:
    """Best-effort enrichment by fetching the company's homepage (and Contact page).

    Never raises: any network/parse failure just returns `company` unchanged
    (logged, not surfaced as a hard error — a single unreachable site should
    not abort an entire discovery job).
    """
    if company.is_mock or not company.website:
        return company

    settings = settings or get_settings()
    headers = {"User-Agent": settings.http_user_agent}

    # The hook runs for the first request and for every redirect, so a
    # public URL can't bounce us into the private network.
    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        headers=headers,
        event_hooks={"request": [block_internal_requests]},
    ) as client:
        home = await _fetch_page(client, company.website)
        if home is None:
            return company
        home_soup, home_text, home_url = home

        if company.company_name == company.website:
            # WebsiteSource seeds company_name with the raw URL as a
            # placeholder (it doesn't know the company's real name yet) —
            # pull a proper one from the page itself now that it's fetched.
            page_title = _page_title(home_soup)
            if page_title:
                company.company_name = _clean_title(page_title) or company.company_name

        meta_description = _meta_description(home_soup)
        if meta_description and (
            not company.description or len(meta_description) > len(company.description)
        ):
            company.description = meta_description

        company.contact_page_url = find_contact_page(home_soup, home_url)
        company.social_profiles = find_social_profiles(home_soup, home_url)

        pages = [(home_soup, home_text)]
        if company.contact_page_url and company.contact_page_url != home_url:
            contact_page = await _fetch_page(client, company.contact_page_url)
            if contact_page is not None:
                contact_soup, contact_text, contact_url = contact_page
                pages.append((contact_soup, contact_text))
                # A contact page's own on-page social links take precedence
                # over anything (rare) found only on the homepage.
                contact_socials = find_social_profiles(contact_soup, contact_url)
                if contact_socials:
                    seen = {p["platform"] for p in company.social_profiles}
                    company.social_profiles += [
                        p for p in contact_socials if p["platform"] not in seen
                    ]

    await _extract_and_validate_contacts(company, pages)
    return company


async def _extract_and_validate_contacts(
    company: DiscoveredCompany, pages: list[tuple[BeautifulSoup, str]]
) -> None:
    """Phase 3/4: pull emails/phones from the fetched pages and validate them."""
    email_candidates: list[str] = []
    tel_candidates: list[str] = []
    text_phone_candidates: list[str] = []
    for soup, text in pages:
        email_candidates.extend(extract_emails(soup, text))
        tel_candidates.extend(extract_tel_link_candidates(soup))
        text_phone_candidates.extend(extract_phone_text_candidates(text))

    email_candidates = list(dict.fromkeys(email_candidates))[:MAX_EMAILS_PER_COMPANY]

    if email_candidates:
        validations = await asyncio.gather(
            *(validate_email_domain(email) for email in email_candidates)
        )
        company.emails = [
            {"email": email, "is_valid": is_valid}
            for email, is_valid in zip(email_candidates, validations, strict=True)
        ]

    company.phones = _validate_and_merge_phones(
        tel_candidates, text_phone_candidates, country=company.country
    )


def _validate_and_merge_phones(
    tel_candidates: list[str], text_candidates: list[str], *, country: str | None
) -> list[dict[str, object]]:
    """`tel:` links are trusted regardless of validation outcome (the page
    author explicitly marked them as a phone number). Plaintext matches are
    noisy — dates, version strings, code samples all match the loose regex
    — so only ones that pass real structural validation are kept."""
    entries: list[dict[str, object]] = []
    seen_digits: set[str] = set()

    for raw in tel_candidates:
        normalized, is_valid = validate_phone(raw, country=country)
        key = re.sub(r"[^0-9]", "", normalized)
        if key and key not in seen_digits:
            seen_digits.add(key)
            entries.append({"phone": normalized, "is_valid": is_valid})

    for raw in text_candidates:
        normalized, is_valid = validate_phone(raw, country=country)
        if not is_valid:
            continue
        key = re.sub(r"[^0-9]", "", normalized)
        if key and key not in seen_digits:
            seen_digits.add(key)
            entries.append({"phone": normalized, "is_valid": True})

    return entries[:MAX_PHONES_PER_COMPANY]


def _page_title(soup: BeautifulSoup) -> str | None:
    tag = soup.find("title")
    if tag and tag.get_text(strip=True):
        return tag.get_text(strip=True)
    return None


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
