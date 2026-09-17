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

from dataclasses import dataclass

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
