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
from concurrent.futures import ThreadPoolExecutor

import dns.resolver
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from app.discovery import email_verification as verification

logger = logging.getLogger("petrolead.discovery.emails")

# dnspython is synchronous, so every MX lookup occupies a thread for as long
# as it takes. Using asyncio's default executor would mean one large batch
# could hold every worker in the process and stall unrelated work, so DNS
# gets its own pool.
_MX_EXECUTOR = ThreadPoolExecutor(max_workers=32, thread_name_prefix="petrolead-mx")

# One resolver for the process. Building a new one per lookup re-reads the
# system resolver configuration every single time.
_RESOLVER = dns.resolver.Resolver()

# How many domains to look up at once, and how long a whole batch may take.
# Domains still outstanding when the budget runs out are reported as
# "unknown" — the honest answer — rather than holding the request open.
MAX_CONCURRENT_MX_LOOKUPS = 32
BATCH_BUDGET_SECONDS = 25.0

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


def extract_emails(soup: BeautifulSoup | None, text: str) -> list[str]:
    """Return deduplicated, plausible business email addresses found on a page.

    `soup` is None for text with no markup, such as a search-result snippet.
    """
    found: set[str] = set()

    for anchor in soup.find_all("a", href=True) if soup is not None else []:
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
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_MX_EXECUTOR, _lookup_mx, domain, timeout)


def _lookup_mx(domain: str, timeout: float) -> bool | None:
    """The blocking half of the check, run on `_MX_EXECUTOR`. The timeout is
    passed per call rather than set on the shared resolver, which several
    threads use at once."""
    try:
        answer = _RESOLVER.resolve(domain, "MX", lifetime=timeout)
        return len(answer) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False
    except Exception as exc:  # noqa: BLE001 — network flakiness, not invalidity
        logger.debug("MX lookup failed for %s: %s", domain, exc)
        return None


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
    # Delegates to the batch path so the grading rules live in one place —
    # two copies of "is this deliverable?" would drift apart.
    return (await verify_emails([email])).results[0]


async def verify_emails(
    emails: list[str], *, timeout: float = 3.0, settings: Settings | None = None
) -> verification.VerificationBatch:
    """Verify a batch of addresses, in input order — blank entries and
    case-insensitive duplicates are dropped (the first spelling wins).

    The work is grouped by domain rather than by address: an MX record
    belongs to the domain, so a list of 500 addresses at a dozen companies
    costs a dozen lookups, not 500. Lookups run concurrently up to
    `MAX_CONCURRENT_MX_LOOKUPS`, and the batch as a whole gives up after
    `BATCH_BUDGET_SECONDS` — domains that didn't finish are reported as
    "unknown", which is what they are.
    """
    unique: dict[str, str] = {}
    for raw in emails:
        email = raw.strip()
        if email and email.lower() not in unique:
            unique[email.lower()] = email
    addresses = list(unique.values())

    # Decide everything that needs no network first: bad syntax, throwaway
    # domains, misspelled providers. These are bounces we can name for free,
    # and they must not cost a DNS query.
    settled: dict[str, verification.Verdict] = {}
    for address in addresses:
        if not is_valid_email_syntax(address):
            settled[address] = verification.Verdict(
                verification.UNDELIVERABLE, "invalid_format"
            )
            continue
        screened = verification.screen(address)
        if screened is not None:
            settled[address] = screened

    # A verification provider, when configured, answers the question DNS
    # cannot: does this mailbox exist? It runs only on addresses that
    # survived screening, so a typo never costs a paid API call.
    provider_checked = 0
    provider = verification.get_provider(settings or get_settings())
    if provider is not None:
        pending = [a for a in addresses if a not in settled]
        if pending:
            try:
                verdicts = await provider.verify(pending)
            except Exception:  # noqa: BLE001 — a provider outage must not 500
                logger.exception("Verification provider failed; falling back to DNS only")
            else:
                # `unknown` from a provider means it couldn't tell us, which
                # is not a verdict. Leaving those out lets the DNS check below
                # still run, so an outage degrades to domain-only grading
                # rather than reporting every address as uncheckable.
                answered = {
                    a: v for a, v in verdicts.items() if v.status != verification.UNKNOWN
                }
                settled.update(answered)
                # Only answered addresses are billable: a failed call gave us
                # nothing, and the DNS check below will cover it for free.
                provider_checked = len(answered)

    # One representative address per domain, for the addresses still open.
    representative: dict[str, str] = {}
    for address in addresses:
        if address not in settled:
            representative.setdefault(address.rsplit("@", 1)[-1].lower(), address)

    accepts_mail: dict[str, bool | None] = {}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_MX_LOOKUPS)

    async def check(domain: str, address: str) -> None:
        async with semaphore:
            accepts_mail[domain] = await validate_email_domain(address, timeout=timeout)

    if representative:
        try:
            await asyncio.wait_for(
                asyncio.gather(*(check(d, a) for d, a in representative.items())),
                timeout=BATCH_BUDGET_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "Verification budget exhausted: checked %d of %d domain(s) in %.0fs",
                len(accepts_mail),
                len(representative),
                BATCH_BUDGET_SECONDS,
            )

    results: list[dict] = []
    for address in addresses:
        decided = settled.get(address)
        if decided is not None:
            results.append(
                {
                    "email": address,
                    "status": decided.status,
                    "reason": decided.reason,
                    "syntax_valid": decided.reason != "invalid_format",
                    "domain_accepts_mail": None,
                }
            )
            continue

        # A domain missing from the map ran out of budget: unknown, not invalid.
        accepts = accepts_mail.get(address.rsplit("@", 1)[-1].lower())
        if accepts is None:
            verdict = verification.Verdict(verification.UNKNOWN, "dns_error")
        elif not accepts:
            verdict = verification.Verdict(verification.UNDELIVERABLE, "no_mail_server")
        else:
            # The domain takes mail. Whether this mailbox does is a question
            # only a verification provider can answer, so with the default
            # `mx` provider this stays `risky` rather than claiming delivery.
            verdict = verification.grade_domain_only(address)
        results.append(
            {
                "email": address,
                "status": verdict.status,
                "reason": verdict.reason,
                "syntax_valid": True,
                "domain_accepts_mail": accepts,
            }
        )
    return verification.VerificationBatch(results=results, provider_checked=provider_checked)
