"""Company name normalization.

Two different sources will rarely spell a company name identically:

    "ABC Petroleum Trading LLC"
    "ABC Petroleum Trading L.L.C."
    "ABC Petroleum Trading"
    "ABC PETROLEUM"

`normalize_company_name` produces a canonical comparison key while the
original, human-facing `company_name` is always preserved untouched
alongside it.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Corporate suffixes stripped for comparison purposes only. Ordered roughly
# longest-first so multi-word suffixes match before their substrings do.
_CORPORATE_SUFFIXES = [
    "limited liability company",
    "public joint stock company",
    "joint stock company",
    "free zone establishment",
    "free zone company",
    "sole proprietorship",
    "general trading",
    "trading company",
    "co kg",
    "gmbh & co kg",
    "gmbh",
    "sarl",
    "s a r l",
    "s.a.r.l",
    "spa",
    "s.p.a",
    "s p a",
    "bv",
    "b.v",
    "nv",
    "n.v",
    "plc",
    "p.l.c",
    "pjsc",
    "fzco",
    "fze",
    "fzc",
    "dmcc",
    "llc",
    "l.l.c",
    "l l c",
    "ltd",
    "limited",
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "llp",
    "l.l.p",
    "lp",
    "pty",
    "ag",
    "kg",
    "oy",
    "ab",
    "as",
    "sa",
    "s.a",
]

# Sorted longest-first so e.g. "limited liability company" is stripped
# before the trailing "company" pattern would otherwise partially match.
_CORPORATE_SUFFIXES.sort(key=len, reverse=True)

_PUNCTUATION_RE = re.compile(r"[.,'’\"()\[\]{}/\\|_+*!?:;]")
_WHITESPACE_RE = re.compile(r"\s+")
_AMPERSAND_RE = re.compile(r"&|\+")


def _strip_suffixes(text: str) -> str:
    """Iteratively remove trailing corporate suffixes (comparison copy only)."""
    changed = True
    while changed:
        changed = False
        for suffix in _CORPORATE_SUFFIXES:
            pattern = rf"\b{re.escape(suffix)}\b\s*$"
            new_text = re.sub(pattern, "", text).strip()
            if new_text != text:
                text = new_text
                changed = True
    return text


def normalize_company_name(company_name: str) -> str:
    """Return a lowercase, punctuation-free, suffix-free comparison key.

    This value is used ONLY for matching/deduplication. The original
    `company_name` supplied by the user/source must always be stored and
    displayed unchanged.
    """
    if not company_name:
        return ""

    text = company_name.strip().lower()
    text = _AMPERSAND_RE.sub(" and ", text)
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _strip_suffixes(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def extract_domain(url: str | None) -> str | None:
    """Extract a normalized registrable-ish domain (host without `www.`) from a URL."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if "//" not in url:
        url = f"//{url}"
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None
