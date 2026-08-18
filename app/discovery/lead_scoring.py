"""Composite lead-quality scoring (Phase 7).

Deliberately transparent rather than a black box: petroleum relevance
(50% of the score) plus how complete and verified the company's contact
footprint is (the remaining 50%, split across having a website/contact
page/social profile, a domain-verified email, and a structurally valid
phone number). Each component is returned separately so the UI can show
*why* a company scored the way it did.
"""

from __future__ import annotations

from dataclasses import dataclass

RELEVANCE_WEIGHT = 0.5
CONTACT_COMPLETENESS_MAX = 20
VERIFIED_EMAIL_MAX = 15
VERIFIED_PHONE_MAX = 15


@dataclass
class LeadScoreResult:
    score: int
    relevance_component: int
    contact_completeness_component: int
    verified_email_component: int
    verified_phone_component: int


def compute_lead_score(
    *,
    relevance_score: int,
    has_website: bool,
    has_contact_page: bool,
    has_social_profile: bool,
    has_verified_email: bool,
    has_verified_phone: bool,
) -> LeadScoreResult:
    relevance_component = round(relevance_score * RELEVANCE_WEIGHT)

    completeness_hits = sum([has_website, has_contact_page, has_social_profile])
    contact_completeness_component = round(CONTACT_COMPLETENESS_MAX * completeness_hits / 3)

    verified_email_component = VERIFIED_EMAIL_MAX if has_verified_email else 0
    verified_phone_component = VERIFIED_PHONE_MAX if has_verified_phone else 0

    total = (
        relevance_component
        + contact_completeness_component
        + verified_email_component
        + verified_phone_component
    )
    score = max(0, min(100, total))

    return LeadScoreResult(
        score=score,
        relevance_component=relevance_component,
        contact_completeness_component=contact_completeness_component,
        verified_email_component=verified_email_component,
        verified_phone_component=verified_phone_component,
    )
