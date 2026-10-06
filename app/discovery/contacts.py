"""Business contact discovery (Phase 2).

Extracts three things, and only from links a company has already
published on its own public website:

    1. A "Contact" page URL, found by scanning the homepage's own links.
    2. Other pages on the same site where companies tend to list addresses
       — About, Team, Leadership, Imprint/Impressum, Legal, Privacy.
    3. Social-profile links (LinkedIn, Facebook, X/Twitter, Instagram,
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

CONTACT_LINK_HINTS = (
    "contact",
    "get-in-touch",
    "reach-us",
    "reachus",
    "enquiry",
    "inquiry",
    # Kontakt (German, Dutch, Nordic, Polish), contato (Portuguese),
    # contatti (Italian). "contacto"/"contactez" already contain "contact".
    "kontakt",
    "contato",
    "contatti",
)

# Pages besides Contact that list addresses, most useful first: who works
# there, then who the company is, then the legal pages that in much of
# Europe must carry a contact address by law (Impressum).
EXTRA_PAGE_HINTS = (
    ("team", "our-people", "people", "staff", "leadership", "management", "directors"),
    ("about", "who-we-are", "company", "uber-uns", "ueber-uns", "quienes-somos", "chi-siamo"),
    ("impressum", "imprint", "legal", "mentions-legales", "aviso-legal"),
    ("privacy", "datenschutz"),
)
_SKIPPED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc", ".docx", ".xls")


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


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def find_extra_pages(
    soup: BeautifulSoup, base_url: str, *, exclude: set[str], limit: int
) -> list[str]:
    """Up to `limit` links on this same site to pages that tend to list
    email addresses (see `EXTRA_PAGE_HINTS`), best first. Only links the
    page actually has — no URL is made up."""
    if limit <= 0:
        return []
    site = _host(base_url)
    ranked: dict[str, int] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href).split("#", 1)[0]
        if _host(absolute) != site or absolute in exclude:
            continue
        path = urlparse(absolute).path.lower()
        if path in ("", "/") or path.endswith(_SKIPPED_EXTENSIONS):
            continue
        haystack = f"{path} {anchor.get_text(strip=True).lower()}"
        for rank, hints in enumerate(EXTRA_PAGE_HINTS):
            if any(hint in haystack for hint in hints):
                ranked[absolute] = min(rank, ranked.get(absolute, rank))
                break
    return sorted(ranked, key=ranked.__getitem__)[:limit]


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
