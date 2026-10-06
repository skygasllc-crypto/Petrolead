"""Finding business emails through outside services.

A specific person's email, given their name and their employer's domain,
from one of the providers chosen by `CONTACT_PROVIDER`:

* `hunter` — Hunter.io, with its own 0-100 confidence score.
* `prospeo` — Prospeo's enrich-person endpoint.
* `apollo` — Apollo's people match.

Apollo can also be asked about a LinkedIn profile URL directly
(`apollo_match`), which needs no search-engine listing of the profile.

When neither finds the person, `guess_person_email` tries the address
formats companies actually use and keeps one only if the verification
provider confirms the mailbox — a guess is never shown as found.

Separately, `find_domain_emails` asks Hunter for every address it knows at
a company's domain, for companies whose own website lists none.

Either way this is a best-effort enrichment on top of the LinkedIn
profile-snippet lookup, and the domain is always one already confirmed by a
public search result (see `company_service._resolve_company_domain`) — never
guessed. When no provider is configured, or a lookup fails, or the match
isn't confident enough, callers simply proceed without an email.

`find_person_email` keeps one shape whichever provider answers:
`{"email": str, "is_valid": bool | None}` or None. That contract is what
company_service and the tests depend on, so the provider choice stays behind
this function rather than leaking upwards.
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.discovery import email_verification as verification
from app.discovery.emails import validate_email_domain

logger = logging.getLogger("petrolead.discovery.email_finder")

HUNTER_ENDPOINT = "https://api.hunter.io/v2/email-finder"
HUNTER_DOMAIN_SEARCH_ENDPOINT = "https://api.hunter.io/v2/domain-search"
APOLLO_MATCH_ENDPOINT = "https://api.apollo.io/api/v1/people/match"
PROSPEO_ENDPOINT = "https://api.prospeo.io/enrich-person"

# Hunter's own 0-100 confidence score. Below this, better to show nothing
# than a low-confidence guess presented as a found email.
MIN_CONFIDENCE = 50

# Prospeo error codes that mean *our account* is broken, not that the person
# couldn't be found. Worth separating in the logs: a run of NO_MATCH is
# normal, a run of these means the integration has stopped working.
_ACCOUNT_ERRORS = {"INVALID_API_KEY", "INSUFFICIENT_CREDITS"}


def _split_name(full_name: str) -> tuple[str, str] | None:
    """Prospeo wants first and last separately; we hold one string. Returns
    None when there aren't two parts to give it."""
    parts = [p for p in full_name.strip().split() if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[-1]


async def _find_via_hunter(*, domain: str, full_name: str, settings: Settings) -> dict | None:
    params = {
        "domain": domain,
        "full_name": full_name,
        "api_key": settings.hunter_io_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(HUNTER_ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning("Hunter email-finder lookup failed for domain=%r", domain, exc_info=True)
        return None

    result = data.get("data") or {}
    email = result.get("email")
    score = result.get("score")
    if not email or score is None or score < MIN_CONFIDENCE:
        return None

    status = (result.get("verification") or {}).get("status")
    is_valid = True if status == "valid" else (False if status == "invalid" else None)
    return {"email": email, "is_valid": is_valid}


async def _find_via_prospeo(*, domain: str, full_name: str, settings: Settings) -> dict | None:
    names = _split_name(full_name)
    if names is None:
        return None
    first, last = names

    payload = {
        "data": {"first_name": first, "last_name": last, "company_website": domain},
        "only_verified_email": False,
        "enrich_mobile": False,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(
                PROSPEO_ENDPOINT,
                json=payload,
                headers={
                    "X-KEY": settings.prospeo_api_key or "",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning("Prospeo email-finder lookup failed for domain=%r", domain, exc_info=True)
        return None

    if data.get("error"):
        code = data.get("error_code")
        if code in _ACCOUNT_ERRORS:
            # Not a missing person — the integration itself has stopped
            # working, and every lookup will fail until it's dealt with.
            logger.error("Prospeo rejected the request: %s", code)
        elif code != "NO_MATCH":
            # INVALID_DATAPOINTS, INVALID_REQUEST, INTERNAL_ERROR, a rate
            # limit: all mean the request we sent was unusable, not that
            # the person couldn't be found. Staying silent would make a
            # broken integration look exactly like an honest miss.
            logger.warning("Prospeo could not process the request: %s", code)
        return None

    email_block = ((data.get("person") or {}).get("email")) or {}
    email = email_block.get("email")
    if not email:
        return None

    # A masked address ("eoghan.*****@intercom.com") is returned when the
    # result isn't revealed. Treating that as found would spend a customer's
    # credit on a string that can never be mailed.
    if email_block.get("revealed") is False or "*" in email:
        logger.info("Prospeo returned a masked address for domain=%r; treating as no match", domain)
        return None

    status = (email_block.get("status") or "").upper()
    is_valid = True if status == "VERIFIED" else (False if status == "INVALID" else None)
    return {"email": email, "is_valid": is_valid}


@dataclass
class ApolloPerson:
    name: str
    title: str | None
    company_name: str | None
    domain: str | None
    email: dict | None


# Apollo's `email_status` values. "verified" was checked by Apollo;
# "guessed"/"extrapolated" come from the company's address format and are
# shown as unconfirmed. Anything else means there's no usable address.
_APOLLO_VERIFIED = {"verified"}
_APOLLO_UNCONFIRMED = {"guessed", "extrapolated", "likely to engage"}
# What Apollo puts in `email` when the plan hasn't unlocked the address.
_APOLLO_LOCKED_MARKER = "email_not_unlocked"


def _apollo_email(person: dict) -> dict | None:
    email = person.get("email")
    if not email or _APOLLO_LOCKED_MARKER in email:
        return None
    status = (person.get("email_status") or "").lower()
    if status in _APOLLO_VERIFIED:
        return {"email": email, "is_valid": True}
    if status in _APOLLO_UNCONFIRMED:
        return {"email": email, "is_valid": None}
    return None


async def apollo_match(
    *,
    settings: Settings,
    linkedin_url: str | None = None,
    full_name: str | None = None,
    domain: str | None = None,
    organization_name: str | None = None,
) -> ApolloPerson | None:
    """Who Apollo has for this LinkedIn URL (or name + employer), or None
    when Apollo isn't configured, has no confident match, or the call
    failed. Never raises. Apollo charges a credit only when it returns
    data."""
    if not settings.apollo_api_key:
        return None
    params = {
        key: value
        for key, value in {
            "linkedin_url": linkedin_url,
            "name": full_name,
            "domain": domain,
            "organization_name": organization_name,
        }.items()
        if value
    }
    if not params:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(
                APOLLO_MATCH_ENDPOINT,
                params=params,
                headers={"x-api-key": settings.apollo_api_key, "Cache-Control": "no-cache"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Apollo people match failed (%s)", type(exc).__name__)
        return None

    if response.status_code in (401, 403):
        # Every lookup will fail the same way until the key is fixed.
        logger.error("Apollo rejected the API key (HTTP %s)", response.status_code)
        return None
    if response.status_code == 429:
        logger.warning("Apollo rate limit or credits exhausted (HTTP 429)")
        return None
    if response.is_error:
        logger.warning("Apollo people match failed (HTTP %s)", response.status_code)
        return None

    try:
        person = response.json().get("person") or {}
    except ValueError:
        logger.warning("Apollo people match returned a non-JSON body")
        return None
    if not person.get("name") or person.get("match_confidence") in ("none", "low"):
        return None

    organization = person.get("organization") or {}
    return ApolloPerson(
        name=person["name"],
        title=person.get("title"),
        company_name=organization.get("name"),
        domain=organization.get("primary_domain"),
        email=_apollo_email(person),
    )


async def find_person_email(*, domain: str, full_name: str, settings: Settings) -> dict | None:
    """Returns `{"email": str, "is_valid": bool | None}`, or None when no
    provider is configured, the lookup failed, or there was no confident
    match. Never raises — an enrichment failure must not fail the lookup."""
    provider = (settings.contact_provider or "hunter").strip().lower()

    if provider == "apollo":
        person = await apollo_match(settings=settings, full_name=full_name, domain=domain)
        return person.email if person else None

    if provider == "prospeo":
        if not settings.prospeo_api_key:
            return None
        return await _find_via_prospeo(domain=domain, full_name=full_name, settings=settings)

    if not settings.hunter_io_api_key:
        return None
    return await _find_via_hunter(domain=domain, full_name=full_name, settings=settings)


# --- Domain search ----------------------------------------------------------

# Hunter returns at most this many addresses per request on most plans, and
# one request costs one credit however many come back.
DOMAIN_SEARCH_LIMIT = 10


async def find_domain_emails(*, domain: str, settings: Settings) -> list[dict]:
    """Addresses Hunter knows at `domain`, most confident first, in the
    usual `{"email", "is_valid"}` shape. Empty when Hunter isn't configured,
    the lookup fails, or it knows nothing confident. Never raises."""
    if not settings.domain_search_enabled or not settings.hunter_io_api_key:
        return []
    params = {
        "domain": domain,
        "limit": DOMAIN_SEARCH_LIMIT,
        "api_key": settings.hunter_io_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(HUNTER_DOMAIN_SEARCH_ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        # No exc_info: httpx's message carries the URL, and with it the key.
        logger.warning("Hunter domain search failed for domain=%r", domain)
        return []

    entries = (data.get("data") or {}).get("emails") or []
    confident = [
        e for e in entries if e.get("value") and (e.get("confidence") or 0) >= MIN_CONFIDENCE
    ]
    confident.sort(key=lambda e: e.get("confidence") or 0, reverse=True)
    found = []
    for entry in confident:
        status = (entry.get("verification") or {}).get("status")
        if status == "invalid":
            continue
        found.append({"email": entry["value"], "is_valid": True if status == "valid" else None})
    return found


# --- Guessing from name formats -------------------------------------------------

# Titles and credentials that turn up in names copied from LinkedIn and
# never appear in an address.
_NAME_NOISE = frozenset(
    {
        "mr", "mrs", "ms", "miss", "dr", "prof", "eng", "engr", "sir",
        "jr", "sr", "ii", "iii", "iv", "phd", "mba", "msc", "bsc", "cpa", "pmp", "pe", "ceng",
    }
)  # fmt: skip
_PARENTHESISED_RE = re.compile(r"\([^)]*\)")

# The formats companies use, most common first (per published studies of
# corporate address formats). Checking stops at the first confirmed one.
_FORMATS = (
    "{first}.{last}",
    "{first}",
    "{f}{last}",
    "{first}{last}",
    "{f}.{last}",
    "{first}{l}",
    "{first}_{last}",
    "{last}.{first}",
    "{last}",
)
# How many guesses to check at once: enough to be quick, few enough that a
# hit early in the list doesn't pay for checks after it.
_GUESS_BATCH = 3


def name_parts(full_name: str) -> tuple[str, str] | None:
    """`(first, last)` as they'd appear in an address — ASCII, lowercase,
    titles and credentials dropped — or None without both."""
    text = _PARENTHESISED_RE.sub(" ", full_name or "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    tokens = []
    for raw in re.split(r"[\s,]+", text.lower()):
        token = re.sub(r"[^a-z\-']", "", raw).replace("'", "").strip("-")
        if token and token.replace(".", "") not in _NAME_NOISE and len(token) > 1:
            tokens.append(token)
    if len(tokens) < 2:
        return None
    return tokens[0].replace("-", ""), tokens[-1].replace("-", "")


def candidate_addresses(full_name: str, domain: str) -> list[str]:
    parts = name_parts(full_name)
    if parts is None:
        return []
    first, last = parts
    values = {"first": first, "last": last, "f": first[0], "l": last[0]}
    return list(dict.fromkeys(f"{fmt.format(**values)}@{domain}" for fmt in _FORMATS))


async def guess_person_email(*, domain: str, full_name: str, settings: Settings) -> dict | None:
    """The first common-format address for this person that the
    verification provider confirms exists, as `{"email", "is_valid": True}`,
    or None. Never raises.

    A catch-all domain accepts every address, so nothing there can be
    confirmed: that's checked first with one made-up address, and guessing
    stops — presenting an unconfirmable guess as found is how lists bounce.
    """
    if not settings.email_guessing_enabled:
        return None
    provider = verification.get_provider(settings)
    if provider is None:
        return None
    candidates = candidate_addresses(full_name, domain)[: settings.email_guess_max_checks]
    if not candidates:
        return None
    try:
        if not await validate_email_domain(candidates[0]):
            return None

        probe = f"no-such-mailbox-{uuid.uuid4().hex[:12]}@{domain}"
        probe_verdict = (await provider.verify([probe]))[probe]
        if probe_verdict.status in (verification.DELIVERABLE, verification.RISKY):
            logger.info("Not guessing at %r: it accepts any address", domain)
            return None

        for start in range(0, len(candidates), _GUESS_BATCH):
            batch = candidates[start : start + _GUESS_BATCH]
            verdicts = await provider.verify(batch)
            for address in batch:
                if verdicts[address].status == verification.DELIVERABLE:
                    return {"email": address, "is_valid": True}
            if any(v.reason == "catch_all" for v in verdicts.values()):
                return None
    except Exception:
        logger.warning("Email guessing failed for domain=%r", domain, exc_info=True)
    return None
