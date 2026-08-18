"""Business email extraction & validation (Phase 3).

Extracts email addresses only from a company's own already-fetched public
pages (homepage + contact page) — from `mailto:` links (high confidence)
and visible page text (regex, lower confidence but common for a published
"info@company.com" style address). This platform never emails anyone and
never confirms a mailbox actually exists; "validation" here means syntax
plus a live MX-record check on the domain (does mail routing exist for
this domain at all) — a public DNS query, not a mailbox probe.
"""

from __future__ import annotations

import asyncio
import logging
import re

import dns.resolver
from bs4 import BeautifulSoup

logger = logging.getLogger("petrolead.discovery.emails")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Domains that show up constantly in extracted "emails" but are never a
# real business contact address — placeholder/theme/tracking domains.
_EXCLUDED_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "sentry.io",
    "sentry-next.wixpress.com",
    "wixpress.com",
    "schema.org",
    "godaddy.com",
    "yourdomain.com",
    "domain.com",
    "email.com",
    "wordpress.com",
    "w3.org",
}
# The email regex occasionally matches inside asset filenames (e.g. a CSS
# background url containing an "@2x.png" retina suffix) — filter those out.
_EXCLUDED_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")

MAX_EMAILS_PER_COMPANY = 5


def extract_emails(soup: BeautifulSoup, text: str) -> list[str]:
    """Return deduplicated, plausible business email addresses found on a page."""
    found: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith("mailto:"):
            address = href[len("mailto:") :].split("?")[0].strip()
            if address:
                found.add(address)

    for match in EMAIL_RE.findall(text or ""):
        found.add(match)

    cleaned: list[str] = []
    for email in found:
        email = email.strip().strip(".,;:")
        if "@" not in email:
            continue
        domain = email.rsplit("@", 1)[-1].lower()
        if domain in _EXCLUDED_DOMAINS:
            continue
        if email.lower().endswith(_EXCLUDED_SUFFIXES):
            continue
        cleaned.append(email)

    return sorted(set(cleaned))


async def validate_email_domain(email: str, *, timeout: float = 3.0) -> bool | None:
    """Check whether the email's domain has mail-routing (MX) records.

    Returns True/False when the check completes, or None when it couldn't
    be determined (DNS timeout, resolver error) — a transient failure is
    not evidence the address is invalid, so callers should treat None as
    "unverified" rather than "invalid".
    """
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1]

    def _lookup() -> bool | None:
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = timeout
            resolver.lifetime = timeout
            answer = resolver.resolve(domain, "MX")
            return len(answer) > 0
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return False
        except Exception as exc:  # noqa: BLE001 — network flakiness, not invalidity
            logger.debug("MX lookup failed for %s: %s", domain, exc)
            return None

    return await asyncio.to_thread(_lookup)
