"""Grading an address into "will it bounce?", and the provider that decides.

The point of verification is to remove addresses that bounce. A DNS MX
lookup can't do that on its own: it proves the *domain* accepts mail, so
`nobody.at.all@shell.com` passes. Confirming a particular mailbox means
asking a service that maintains mail infrastructure and reputation for it.

So verification has two layers:

1. Checks that need nothing but the address — syntax, disposable domains,
   obvious typos, role accounts. These are free and catch a real share of
   bounces before any provider is called.
2. A provider that confirms the mailbox. `EMAIL_VERIFY_PROVIDER=mx` (the
   default) has none, and is honest about it: every well-formed address at
   a live domain comes back `risky` with reason `domain_only`, never
   `deliverable`. Configure a real provider to get verdicts.

No provider returns 100% certainty — a mailbox can be full, or deleted an
hour after the check — so `deliverable` means "accepted at the time we
asked", and the grading keeps `risky` separate from `deliverable` rather
than rounding it up.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("petrolead.discovery.email_verification")

# --- Statuses -------------------------------------------------------------
# deliverable   the mailbox accepted mail when we asked
# undeliverable it will bounce: bad syntax, dead domain, disposable, typo
# risky         it might bounce: catch-all domain, role account, unchecked
# unknown       we couldn't find out (DNS failure, provider error, timeout)
DELIVERABLE = "deliverable"
UNDELIVERABLE = "undeliverable"
RISKY = "risky"
UNKNOWN = "unknown"

# Only this status is safe to export or send to.
SAFE_TO_SEND = {DELIVERABLE}


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str


# Free, throwaway mailboxes: mail sent to them is pointless even when it is
# technically delivered. A starter list — extend it as you meet new ones.
DISPOSABLE_DOMAINS = frozenset(
    {
        "10minutemail.com",
        "dispostable.com",
        "fakeinbox.com",
        "getnada.com",
        "guerrillamail.com",
        "mailcatch.com",
        "maildrop.cc",
        "mailinator.com",
        "mailnesia.com",
        "sharklasers.com",
        "temp-mail.org",
        "tempmail.com",
        "throwawaymail.com",
        "trashmail.com",
        "yopmail.com",
    }
)

# Misspellings of the big consumer providers. These never resolve to a real
# mailbox, so they're a bounce waiting to happen rather than merely risky.
DOMAIN_TYPOS = {
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmail.con": "gmail.com",
    "gnail.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmail.con": "hotmail.com",
    "outlok.com": "outlook.com",
    "outllook.com": "outlook.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "iclou.com": "icloud.com",
}

# Shared inboxes rather than a person. They often exist — so they're not
# undeliverable — but they attract spam filtering and complaints, and a
# reply is far less likely. Worth separating from a real person's address.
ROLE_PREFIXES = frozenset(
    {
        "abuse",
        "accounts",
        "admin",
        "billing",
        "careers",
        "contact",
        "enquiries",
        "help",
        "hello",
        "hr",
        "info",
        "inquiries",
        "jobs",
        "mail",
        "marketing",
        "no-reply",
        "noreply",
        "office",
        "postmaster",
        "sales",
        "support",
        "team",
        "webmaster",
    }
)


def local_part(address: str) -> str:
    return address.rsplit("@", 1)[0].lower()


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower()


def is_disposable(address: str) -> bool:
    return domain_of(address) in DISPOSABLE_DOMAINS


def is_role_account(address: str) -> bool:
    # Strip any +tag before comparing, so "sales+eu@" still reads as a role.
    return local_part(address).split("+", 1)[0] in ROLE_PREFIXES


def suspected_typo(address: str) -> str | None:
    """The domain this was probably meant to be, if it's a known misspelling."""
    return DOMAIN_TYPOS.get(domain_of(address))


def screen(address: str) -> Verdict | None:
    """Grade an address without touching the network. Returns None when
    nothing is decidable yet and a lookup is still needed."""
    if is_disposable(address):
        return Verdict(UNDELIVERABLE, "disposable_domain")
    typo = suspected_typo(address)
    if typo is not None:
        return Verdict(UNDELIVERABLE, "typo_suspected")
    return None


def grade_domain_only(address: str) -> Verdict:
    """The verdict when the domain accepts mail but nothing checked the
    mailbox. Deliberately not `deliverable`: that is the claim we cannot
    make without a provider, and rounding it up is what produces bounces."""
    if is_role_account(address):
        return Verdict(RISKY, "role_account")
    return Verdict(RISKY, "domain_only")


# --- Providers ------------------------------------------------------------

MILLIONVERIFIER_URL = "https://api.millionverifier.com/api/v3"
# Their per-address timeout, in seconds. Their API accepts 2-60.
PROVIDER_TIMEOUT_SECONDS = 20
# Addresses are checked one request each, so cap how many run at once.
MAX_CONCURRENT_PROVIDER_CALLS = 10

# How MillionVerifier's `result` maps onto our four verdicts.
#
# catch_all is the one that matters: the server accepts every address, so
# acceptance proves nothing about that mailbox. Grading it deliverable is
# precisely how a verified list still bounces, so it stays risky.
_MILLIONVERIFIER_RESULTS = {
    "ok": Verdict(DELIVERABLE, "mailbox_confirmed"),
    "invalid": Verdict(UNDELIVERABLE, "mailbox_not_found"),
    "disposable": Verdict(UNDELIVERABLE, "disposable_domain"),
    "catch_all": Verdict(RISKY, "catch_all"),
    "unknown": Verdict(UNKNOWN, "provider_error"),
    "unverified": Verdict(UNKNOWN, "provider_error"),
}


class MillionVerifierProvider:
    """Confirms whether an individual mailbox exists.

    One request per address. A failure is reported as `unknown` for that
    address rather than raised, so one bad response can't discard a batch of
    500 that otherwise succeeded.
    """

    name = "millionverifier"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def verify(self, addresses: list[str]) -> dict[str, Verdict]:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROVIDER_CALLS)
        results: dict[str, Verdict] = {}

        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT_SECONDS + 10) as client:

            async def check(address: str) -> None:
                async with semaphore:
                    results[address] = await self._verify_one(client, address)

            await asyncio.gather(*(check(a) for a in addresses))
        return results

    async def _verify_one(self, client: httpx.AsyncClient, address: str) -> Verdict:
        try:
            response = await client.get(
                MILLIONVERIFIER_URL,
                params={
                    "api": self._api_key,
                    "email": address,
                    "timeout": PROVIDER_TIMEOUT_SECONDS,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Verification provider failed for %s: %s", address, exc)
            return Verdict(UNKNOWN, "provider_error")

        if payload.get("error"):
            logger.warning("Verification provider error for %s: %s", address, payload["error"])
            return Verdict(UNKNOWN, "provider_error")

        verdict = _MILLIONVERIFIER_RESULTS.get(payload.get("result"))
        if verdict is None:
            logger.warning("Unrecognised provider result %r", payload.get("result"))
            return Verdict(UNKNOWN, "provider_error")

        # A confirmed shared inbox is real but still a poor thing to mail, so
        # it is separated from a person's address rather than called good.
        if verdict.status == DELIVERABLE and payload.get("role"):
            return Verdict(RISKY, "role_account")
        return verdict


_PROVIDERS = {MillionVerifierProvider.name: MillionVerifierProvider}


def get_provider(settings) -> MillionVerifierProvider | None:
    """The configured mailbox-checking provider, or None for DNS-only.

    Returns None when no key is set even if a provider is named: without
    credentials it could only fail every address, and reporting everything
    as `unknown` would be worse than honestly saying nothing was checked.
    """
    name = (settings.email_verify_provider or "mx").strip().lower()
    if name == "mx":
        return None
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        return None
    if not settings.email_verify_api_key:
        logger.warning("EMAIL_VERIFY_PROVIDER=%s is set but no API key is configured", name)
        return None
    return provider_cls(settings.email_verify_api_key)
