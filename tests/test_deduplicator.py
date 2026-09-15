import pytest

from app.database.models import Company, User
from app.discovery.deduplicator import find_match, is_confident_match
from app.discovery.normalizer import normalize_company_name
from app.discovery.types import DiscoveredCompany


def _user(db_session, email: str) -> User:
    user = User(email=email, hashed_password="not-a-real-hash")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def owner(db_session) -> User:
    return _user(db_session, "owner@example.com")


def _seed_company(db_session, owner: User, **overrides) -> Company:
    defaults = dict(
        owner_id=owner.id,
        company_name="ABC Petroleum Trading LLC",
        normalized_name=normalize_company_name("ABC Petroleum Trading LLC"),
        country="United Arab Emirates",
        city="Dubai",
        website="https://abcpetroleum.com",
        domain="abcpetroleum.com",
        industry="Petroleum Trading",
        relevance_score=80,
    )
    defaults.update(overrides)
    company = Company(**defaults)
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


class TestDeduplication:
    def test_same_company_different_source_is_merged_via_domain(self, db_session, owner):
        existing = _seed_company(db_session, owner)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading",  # slightly different spelling
            website="https://www.abcpetroleum.com/about",  # same domain
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate, owner.id)
        assert is_confident_match(match)
        assert match.company.id == existing.id

    def test_same_normalized_name_and_compatible_location_is_merged(self, db_session, owner):
        existing = _seed_company(db_session, owner, website=None, domain=None)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading L.L.C.",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate, owner.id)
        assert is_confident_match(match)
        assert match.company.id == existing.id

    def test_conflicting_location_keeps_records_separate(self, db_session, owner):
        _seed_company(db_session, owner, website=None, domain=None)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading LLC",
            country="Nigeria",  # actively conflicts with the seeded UAE company
            source="search:mock",
        )
        match = find_match(db_session, candidate, owner.id)
        assert not is_confident_match(match)

    def test_unrelated_company_is_not_merged(self, db_session, owner):
        _seed_company(db_session, owner)
        candidate = DiscoveredCompany(
            company_name="Zenith Renewable Energy Cooperative",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate, owner.id)
        assert not is_confident_match(match)
        assert match.company is None

    def test_low_confidence_never_auto_merges(self, db_session, owner):
        _seed_company(db_session, owner, website=None, domain=None)
        # Same country, loosely similar name, but not similar enough to merge.
        candidate = DiscoveredCompany(
            company_name="ABC Global Holdings",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate, owner.id)
        assert not is_confident_match(match)

    def test_another_accounts_company_never_matches(self, db_session, owner):
        # Each account's companies are private: the same company saved by
        # someone else must not count as "already saved" for this account.
        someone_else = _user(db_session, "someone-else@example.com")
        _seed_company(db_session, someone_else)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading LLC",
            website="https://abcpetroleum.com",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate, owner.id)
        assert match.company is None
        assert is_confident_match(find_match(db_session, candidate, someone_else.id))
