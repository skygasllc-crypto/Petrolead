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


# Structural check for a single address typed in by a user — stricter than
# EMAIL_RE, which is tuned for finding addresses inside page text.
_ADDRESS_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)


def is_valid_email_syntax(email: str) -> bool:
    """True if `email` is a structurally plausible address (practical, not full RFC 5322)."""
    if len(email) > 254 or ".." in email or email.count("@") != 1:
        return False
    local = email.split("@", 1)[0]
    if len(local) > 64 or local.startswith(".") or local.endswith("."):
        return False
    return bool(_ADDRESS_RE.match(email))


async def verify_email(email: str) -> dict:
    """Verify one address: syntax first, then an MX check on its domain.

    Status is `valid` (well-formed and the domain accepts mail),
    `invalid_format`, `no_mail_server` (the domain has no MX records) or
    `unknown` (the DNS check couldn't complete). Like everything in this
    module it never contacts the mailbox — `valid` means the domain can
    receive mail, not that this particular mailbox exists.
    """
    email = email.strip()
    if not is_valid_email_syntax(email):
        return {
            "email": email,
            "status": "invalid_format",
            "syntax_valid": False,
            "domain_accepts_mail": None,
        }

    accepts_mail = await validate_email_domain(email)
    if accepts_mail is None:
        status = "unknown"
    else:
        status = "valid" if accepts_mail else "no_mail_server"
    return {
        "email": email,
        "status": status,
        "syntax_valid": True,
        "domain_accepts_mail": accepts_mail,
    }


async def verify_emails(emails: list[str]) -> list[dict]:
    """Verify several addresses concurrently, in input order — blank entries
    and case-insensitive duplicates are dropped (the first spelling wins)."""
    unique: dict[str, str] = {}
    for raw in emails:
        email = raw.strip()
        if email and email.lower() not in unique:
            unique[email.lower()] = email
    return list(await asyncio.gather(*(verify_email(email) for email in unique.values())))
