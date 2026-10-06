"""The shared contact directory: every business address discovery finds,
and what each mail domain's addresses look like.

Every search adds to it, and every later lookup checks it first. A person
already found is returned without spending anything; a company whose
address format is known gets one targeted check instead of eight guesses.
This is what makes the platform's data its own rather than a re-sale of a
provider's.

Only discovery's own finds are recorded — never addresses a customer typed
or pasted in. Opted-out addresses are deleted and never stored again.
Recording is best-effort: a failure here is logged and the lookup that
triggered it carries on.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ContactRecord, EmailDomain, SuppressedEmail, utcnow
from app.discovery import email_verification as verification
from app.discovery.email_finder import DomainHints, address_for, format_of, name_parts
from app.discovery.normalizer import extract_domain
from app.discovery.search import B2B_DIRECTORY_DOMAINS
from app.discovery.types import DiscoveredCompany

logger = logging.getLogger("petrolead.services.contact_directory")

# How many known addresses must share a format before an address built from
# it is offered without a mailbox check. One could be a coincidence.
MIN_PATTERN_EVIDENCE = 2

# Hosts that turn up as a result's "website" but are never a company's own
# site: social platforms and B2B directories.
NOT_A_COMPANY_SITE = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    *B2B_DIRECTORY_DOMAINS,
}


def site_domain(url: str | None) -> str | None:
    """The domain of a company's own website, or None for a social or
    directory page."""
    domain = extract_domain(url)
    if not domain or any(blocked in domain for blocked in NOT_A_COMPANY_SITE):
        return None
    return domain


def company_mail_domain(candidate: DiscoveredCompany) -> str | None:
    """A result's own mail domain, or None for mock data and for a
    "website" that is really a social or directory page."""
    if candidate.is_mock:
        return None
    return site_domain(candidate.website)


def _name_key(full_name: str | None) -> str | None:
    parts = name_parts(full_name or "")
    return " ".join(parts) if parts else None


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def _separator_format(email: str) -> str | None:
    """`jane.doe@` or `jane_doe@` reads as a first/last format even with no
    name to compare against, which lets a company's format be learned from
    the addresses on its own website."""
    local = email.rsplit("@", 1)[0].lower()
    for separator, fmt in ((".", "{first}.{last}"), ("_", "{first}_{last}")):
        parts = local.split(separator)
        if len(parts) == 2 and all(p.isalpha() and len(p) > 1 for p in parts):
            if not verification.is_role_account(f"{parts[0]}@x") and not (
                verification.is_role_account(f"{parts[1]}@x")
            ):
                return fmt
    return None


def is_suppressed(db: Session, email: str) -> bool:
    return (
        db.execute(
            select(SuppressedEmail.id).where(SuppressedEmail.email == email.strip().lower())
        ).first()
        is not None
    )


def suppress(db: Session, email: str) -> None:
    """Honor an opt-out: delete the address and refuse it from now on."""
    email = email.strip().lower()
    record = db.execute(
        select(ContactRecord).where(ContactRecord.email == email)
    ).scalar_one_or_none()
    if record is not None:
        db.delete(record)
    if not is_suppressed(db, email):
        db.add(SuppressedEmail(email=email))
    db.commit()


def _domain_row(db: Session, domain: str) -> EmailDomain:
    row = db.get(EmailDomain, domain)
    if row is None:
        row = EmailDomain(domain=domain, pattern_counts={})
        db.add(row)
        # Flushed straight away so the next lookup in the same batch finds
        # it, rather than adding a second row for the same domain.
        db.flush()
    return row


def _count_format(db: Session, domain: str, fmt: str) -> None:
    row = _domain_row(db, domain)
    # Reassigned rather than mutated in place: a JSON column only notices
    # a change when the attribute itself is set.
    counts = dict(row.pattern_counts or {})
    counts[fmt] = counts.get(fmt, 0) + 1
    row.pattern_counts = counts
    row.updated_at = utcnow()


def _record_one(
    db: Session,
    *,
    email: str,
    is_valid: bool | None,
    candidate: DiscoveredCompany,
    source: str,
) -> None:
    email = email.strip().lower()
    if "@" not in email or is_valid is False or is_suppressed(db, email):
        return
    domain = _domain_of(email)

    # The address is this person's only when it fits their name. A lookup
    # can turn up other addresses too (a snippet's info@), and pinning
    # those to the person would teach the directory something false.
    person_format = (
        format_of(candidate.contact_person_name, email) if candidate.contact_person_name else None
    )
    learned_format = person_format or _separator_format(email)

    record = db.execute(
        select(ContactRecord).where(ContactRecord.email == email)
    ).scalar_one_or_none()
    if record is None:
        db.add(
            ContactRecord(
                email=email,
                domain=domain,
                full_name=candidate.contact_person_name if person_format else None,
                name_key=_name_key(candidate.contact_person_name) if person_format else None,
                title=candidate.contact_person_title if person_format else None,
                company_name=candidate.company_name,
                source=source,
                source_url=candidate.source_url,
                is_valid=is_valid,
            )
        )
        # Flushed so the same address later in this batch updates this row.
        db.flush()
        # Each address counts towards its domain's format once, when first
        # seen — seeing the same address again is no new evidence.
        if learned_format:
            _count_format(db, domain, learned_format)
        return

    record.last_seen_at = utcnow()
    record.times_seen += 1
    if is_valid and not record.is_valid:
        record.is_valid = True
    if person_format and not record.name_key:
        record.full_name = candidate.contact_person_name
        record.name_key = _name_key(candidate.contact_person_name)
        record.title = candidate.contact_person_title
    if candidate.company_name and not record.company_name:
        record.company_name = candidate.company_name


def record_candidates(db: Session, candidates: list[DiscoveredCompany]) -> None:
    """Add every address these results carry to the directory, noting each
    result's source. Mock data is never recorded. Never raises."""
    try:
        for candidate in candidates:
            if candidate.is_mock:
                continue
            for entry in candidate.emails:
                _record_one(
                    db,
                    email=str(entry.get("email") or ""),
                    is_valid=entry.get("is_valid"),
                    candidate=candidate,
                    source=(candidate.source or "unknown")[:50],
                )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Couldn't record found addresses in the directory", exc_info=True)


def known_person_email(db: Session, *, domain: str, full_name: str) -> dict | None:
    """This person's address at `domain`, if the directory already has it."""
    key = _name_key(full_name)
    if key is None:
        return None
    record = (
        db.execute(
            select(ContactRecord)
            .where(ContactRecord.domain == domain.lower(), ContactRecord.name_key == key)
            .order_by(ContactRecord.is_valid.desc(), ContactRecord.last_seen_at.desc())
        )
        .scalars()
        .first()
    )
    if record is None:
        return None
    return {"email": record.email, "is_valid": record.is_valid}


def known_domain_emails(db: Session, domain: str, *, limit: int) -> list[dict]:
    """Addresses already found at `domain`, confirmed ones first."""
    records = db.execute(
        select(ContactRecord)
        .where(ContactRecord.domain == domain.lower())
        .order_by(ContactRecord.is_valid.desc(), ContactRecord.times_seen.desc())
        .limit(limit)
    ).scalars()
    return [{"email": r.email, "is_valid": r.is_valid} for r in records]


def domain_hints(db: Session, domain: str) -> DomainHints:
    row = db.get(EmailDomain, domain.lower())
    if row is None:
        return DomainHints()
    return DomainHints(preferred_format=_best_format(row), catch_all=row.is_catch_all)


def _best_format(row: EmailDomain) -> str | None:
    counts = row.pattern_counts or {}
    if not counts:
        return None
    return max(counts, key=counts.__getitem__)


def remember_hints(db: Session, domain: str, hints: DomainHints) -> None:
    """Keep a catch-all answer that guessing paid for. Never raises."""
    if hints.catch_all is None:
        return
    try:
        row = _domain_row(db, domain.lower())
        if row.is_catch_all != hints.catch_all:
            row.is_catch_all = hints.catch_all
            row.catch_all_checked_at = utcnow()
            row.updated_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Couldn't remember catch-all status for %r", domain, exc_info=True)


def pattern_email(db: Session, *, domain: str, full_name: str) -> dict | None:
    """This person's address in the company's established format, offered
    unconfirmed — what's shown when the format is well evidenced but the
    mailbox can't be checked (no verifier, or a catch-all server)."""
    row = db.get(EmailDomain, domain.lower())
    if row is None:
        return None
    fmt = _best_format(row)
    if fmt is None or (row.pattern_counts or {}).get(fmt, 0) < MIN_PATTERN_EVIDENCE:
        return None
    address = address_for(full_name, domain.lower(), fmt)
    if address is None or is_suppressed(db, address):
        return None
    return {"email": address, "is_valid": None}
