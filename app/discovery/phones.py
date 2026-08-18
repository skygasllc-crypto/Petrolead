"""Business telephone extraction & validation (Phase 4).

Extracts phone-number candidates only from a company's own already-fetched
public pages (homepage + contact page) — from `tel:` links (high
confidence) and visible page text (regex, lower confidence). Validation is
purely syntactic/structural via Google's libphonenumber (through the
`phonenumbers` package): does this look like a real, dialable number for
its country. No call is ever placed and no external service is contacted.
"""

from __future__ import annotations

import re

import phonenumbers

# Company country (as stored on `Company.country`) -> ISO 3166-1 alpha-2,
# used as a parsing hint for numbers written without a country code.
# Mirrors frontend/src/lib/constants.js COUNTRIES.
COUNTRY_TO_ISO2: dict[str, str] = {
    "United Arab Emirates": "AE",
    "Saudi Arabia": "SA",
    "Qatar": "QA",
    "Kuwait": "KW",
    "Bahrain": "BH",
    "Oman": "OM",
    "Nigeria": "NG",
    "Angola": "AO",
    "Egypt": "EG",
    "Algeria": "DZ",
    "Libya": "LY",
    "South Africa": "ZA",
    "United States": "US",
    "Canada": "CA",
    "Mexico": "MX",
    "Brazil": "BR",
    "Venezuela": "VE",
    "United Kingdom": "GB",
    "Netherlands": "NL",
    "Norway": "NO",
    "Russia": "RU",
    "Turkey": "TR",
    "China": "CN",
    "India": "IN",
    "Singapore": "SG",
    "Indonesia": "ID",
    "Malaysia": "MY",
    "South Korea": "KR",
    "Japan": "JP",
    "Australia": "AU",
    "Kazakhstan": "KZ",
    "Azerbaijan": "AZ",
    "Georgia": "GE",
}

# Loose candidate pattern — deliberately permissive; `phonenumbers` does the
# real validation afterward, this just avoids running it on plain sentences.
PHONE_CANDIDATE_RE = re.compile(r"(\+?\d[\d()\-.\s]{6,17}\d)")

MAX_PHONES_PER_COMPANY = 5


def _digits_key(raw: str) -> str:
    return re.sub(r"[^0-9+]", "", raw)


def extract_phone_candidates(soup, text: str) -> list[str]:
    """Return deduplicated, plausible phone-number strings found on a page."""
    found: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith("tel:"):
            number = href[len("tel:") :].strip()
            if number:
                found.append(number)

    for match in PHONE_CANDIDATE_RE.findall(text or ""):
        digits_only = re.sub(r"[^0-9]", "", match)
        if len(digits_only) >= 7:
            found.append(match.strip())

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in found:
        key = _digits_key(candidate)
        if key and key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def validate_phone(raw: str, *, country: str | None = None) -> tuple[str, bool]:
    """Validate a candidate number, returning (normalized_or_raw, is_valid).

    On success, the number is normalized to E.164 (e.g. "+971 4 xxx xxxx").
    On failure it's returned unchanged with `is_valid=False` — still worth
    keeping (a human can judge it), just not confirmed as dialable.
    """
    region = COUNTRY_TO_ISO2.get(country or "")
    try:
        parsed = phonenumbers.parse(raw, region or None)
    except phonenumbers.NumberParseException:
        return raw, False

    if phonenumbers.is_valid_number(parsed):
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164), True
    return raw, False
