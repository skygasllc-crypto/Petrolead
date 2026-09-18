"""Finding a specific person's business email, given their name and their
employer's domain.

Two providers, chosen by `CONTACT_PROVIDER`:

* `hunter` — Hunter.io, with its own 0-100 confidence score.
* `prospeo` — Prospeo's enrich-person endpoint.

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

import httpx

from app.config import Settings

logger = logging.getLogger("petrolead.discovery.email_finder")

HUNTER_ENDPOINT = "https://api.hunter.io/v2/email-finder"
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


async def find_person_email(*, domain: str, full_name: str, settings: Settings) -> dict | None:
    """Returns `{"email": str, "is_valid": bool | None}`, or None when no
    provider is configured, the lookup failed, or there was no confident
    match. Never raises — an enrichment failure must not fail the lookup."""
    provider = (settings.contact_provider or "hunter").strip().lower()

    if provider == "prospeo":
        if not settings.prospeo_api_key:
            return None
        return await _find_via_prospeo(domain=domain, full_name=full_name, settings=settings)

    if not settings.hunter_io_api_key:
        return None
    return await _find_via_hunter(domain=domain, full_name=full_name, settings=settings)
