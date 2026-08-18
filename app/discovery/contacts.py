"""Business contact discovery (Phase 2).

Extracts exactly two things, and only from links a company has already
published on its own public website:

    1. A "Contact" page URL, found by scanning the homepage's own links.
    2. Social-profile links (LinkedIn, Facebook, X/Twitter, Instagram,
       YouTube) the company put in its own page markup.

This is deliberately narrow. It never guesses, infers, or fabricates a
contact page or profile — a link either exists in the page's HTML or it
doesn't. It never extracts emails or phone numbers (see Phase 3/4), and
never visits anything other than the public page already fetched by the
discovery pipeline — no login walls, no CAPTCHAs, no private data.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Hostname suffix -> canonical platform label.
SOCIAL_DOMAINS: dict[str, str] = {
    "linkedin.com": "linkedin",
    "facebook.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
}

CONTACT_LINK_HINTS = ("contact", "get-in-touch", "reach-us", "reachus", "enquiry", "inquiry")


def find_contact_page(soup: BeautifulSoup, base_url: str) -> str | None:
    """Return the first link on the page that looks like a "Contact" page."""
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        text = anchor.get_text(strip=True).lower()
        haystack = f"{href.lower()} {text}"
        if any(hint in haystack for hint in CONTACT_LINK_HINTS):
            return urljoin(base_url, href)
    return None


def find_social_profiles(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Return social-platform links published on the page, one per platform."""
    found: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        host = (urlparse(absolute).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        for domain, platform in SOCIAL_DOMAINS.items():
            if (host == domain or host.endswith(f".{domain}")) and platform not in found:
                found[platform] = absolute
                break
    return [{"platform": platform, "url": url} for platform, url in found.items()]
