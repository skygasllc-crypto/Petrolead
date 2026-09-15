"""Fallback for a personal social-profile URL pasted into "paste a link".

A URL like `https://linkedin.com/in/someone` is a *person's* profile, not a
company page — and it's login-gated, so PetroLead never fetches it directly
(same boundary as everywhere else in this project; see `discovery/sources.py`
and `discovery/contacts.py`). Instead, this queries the configured
`SearchProvider` for whatever public snippet a search engine has indexed for
that exact URL — the same trust model already used for `SocialSource` — and
parses out a name/title/company if the snippet has one. Never a guarantee:
most profile URLs won't be indexed with a useful snippet, and this never
tries to guess or scrape around that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_LINKEDIN_PERSONAL_RE = re.compile(
    r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[^/?#]+/?", re.IGNORECASE
)

# LinkedIn snippet titles are conventionally "{Name} - {Headline} | LinkedIn",
# with the headline itself often "{Title} at {Company}". Trailing separator
# + platform name is stripped first; " - " then splits name / headline.
_TRAILING_PLATFORM_RE = re.compile(r"\s*[|\-–—]\s*linkedin\s*$", re.IGNORECASE)
_TITLE_AT_COMPANY_RE = re.compile(r"^(?P<title>.+?)\s+at\s+(?P<company>.+)$", re.IGNORECASE)
# Search engines cut long titles/snippets off with an ellipsis — a company
# name that ends in one is incomplete and must not be reported.
_TRUNCATED_RE = re.compile(r"(?:\.\.\.|…)$")
# Google's LinkedIn snippets often carry an explicit, labeled employer field:
# "Headline · Experience: Northern Pipeline Construction · Location: ...".
# Unlike free headline text this is unambiguous, so it's safe to trust.
_SNIPPET_EXPERIENCE_RE = re.compile(r"\bExperience:\s*(?P<company>[^·•|]+?)\s*(?:[·•|]|$)")


def _complete(value: str | None) -> str | None:
    if not value or _TRUNCATED_RE.search(value):
        return None
    return value


def detect_personal_profile_platform(url: str) -> str | None:
    """Returns a platform name (e.g. "linkedin") if `url` is a personal
    profile URL this module knows how to fall back on, else None.

    Deliberately narrow: only LinkedIn's `/in/` path is unambiguous
    (`linkedin.com/company/...` is a business page, handled elsewhere).
    Twitter/X and Facebook profile URLs don't have a reliable equivalent
    marker, so they're left to the normal website-fetch path.
    """
    if _LINKEDIN_PERSONAL_RE.match(url):
        return "linkedin"
    return None


@dataclass
class ParsedProfile:
    name: str
    title: str | None
    company_name: str | None


def parse_profile_snippet(raw_title: str, snippet: str = "") -> ParsedProfile | None:
    """Best-effort parse of a search-result title for a profile URL.

    Deliberately conservative about the `company_name` it returns:
    LinkedIn's indexed titles don't consistently distinguish current
    employer from education/other headline text once you get past the
    explicit "{Title} at {Company}" phrasing or a clearly 3-segment
    "{Name} - {Title} - {Company}" form — a shorter 2-segment snippet
    ("{Name} - {Something}") is genuinely ambiguous (that "something"
    could just as easily be a school or a tagline as an employer), so
    that case is left as name-only rather than guessed.

    When the title names no company, falls back to an explicit
    "Experience: {Company}" field in the result's `snippet` text — a
    labeled employer, not a guess. A company cut off by the search engine
    ("Falcon Petrol...") is never reported.

    Returns None if the title doesn't look like a name/headline snippet at
    all (e.g. the platform's generic homepage title came back instead).
    """
    text = _TRAILING_PLATFORM_RE.sub("", raw_title).strip()
    if not text:
        return None

    segments = [s.strip() for s in text.split(" - ") if s.strip()]
    if not segments:
        return None

    name = segments[0]
    title: str | None = None
    company: str | None = None

    if len(segments) >= 2:
        at_match = _TITLE_AT_COMPANY_RE.match(segments[1])
        if at_match:
            title = at_match.group("title").strip()
            company = at_match.group("company").strip()
        elif len(segments) >= 3:
            title = segments[1]
            company = segments[2]
        # else: only a 2-segment snippet with no explicit "at Company" —
        # too ambiguous to guess a company from, left as name-only.

    company = _complete(company)
    if company is None:
        experience = _SNIPPET_EXPERIENCE_RE.search(snippet)
        if experience:
            company = _complete(experience.group("company").strip())

    return ParsedProfile(name=name, title=title, company_name=company)


def build_profile_snippet_query(url: str) -> str:
    """A `site:`-scoped query targeting this exact profile URL — never a
    fetch of the page itself, just what a search engine already indexed."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"site:{parsed.netloc}{path}"
