"""Hunter.io Email Finder (https://hunter.io/) — resolves a specific
person's likely business email given their name and employer's domain.

Only ever called with a domain already confirmed via a public search-engine
result (see `company_service._resolve_company_domain`) — never guesses a
domain, and this is strictly a best-effort enrichment layered on top of the
LinkedIn profile-snippet lookup (`company_service._preview_from_profile_snippet`):
if it's not configured, fails, or comes back with a low-confidence match,
callers just proceed without an email, same as any other optional source.
"""

from __future__ import annotations

import logging

import httpx

from app.config import Settings

logger = logging.getLogger("petrolead.discovery.email_finder")

ENDPOINT = "https://api.hunter.io/v2/email-finder"

# Hunter's own 0-100 confidence score. Below this, better to show nothing
# than a low-confidence guess presented as a found email.
MIN_CONFIDENCE = 50


async def find_person_email(*, domain: str, full_name: str, settings: Settings) -> dict | None:
    """Returns `{"email": str, "is_valid": bool | None}`, or None if Hunter
    isn't configured, the lookup failed, or there was no confident match."""
    if not settings.hunter_io_api_key:
        return None

    params = {
        "domain": domain,
        "full_name": full_name,
        "api_key": settings.hunter_io_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning(
            "Hunter.io email-finder lookup failed for domain=%r", domain, exc_info=True
        )
        return None

    result = data.get("data") or {}
    email = result.get("email")
    score = result.get("score")
    if not email or score is None or score < MIN_CONFIDENCE:
        return None

    status = (result.get("verification") or {}).get("status")
    is_valid = True if status == "valid" else (False if status == "invalid" else None)
    return {"email": email, "is_valid": is_valid}
