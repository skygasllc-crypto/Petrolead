from app.database.models import Company
from app.discovery.deduplicator import find_match, is_confident_match
from app.discovery.normalizer import normalize_company_name
from app.discovery.types import DiscoveredCompany


def _seed_company(db_session, **overrides) -> Company:
    defaults = dict(
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
    def test_same_company_different_source_is_merged_via_domain(self, db_session):
        existing = _seed_company(db_session)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading",  # slightly different spelling
            website="https://www.abcpetroleum.com/about",  # same domain
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate)
        assert is_confident_match(match)
        assert match.company.id == existing.id

    def test_same_normalized_name_and_compatible_location_is_merged(self, db_session):
        existing = _seed_company(db_session, website=None, domain=None)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading L.L.C.",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate)
        assert is_confident_match(match)
        assert match.company.id == existing.id

    def test_conflicting_location_keeps_records_separate(self, db_session):
        _seed_company(db_session, website=None, domain=None)
        candidate = DiscoveredCompany(
            company_name="ABC Petroleum Trading LLC",
            country="Nigeria",  # actively conflicts with the seeded UAE company
            source="search:mock",
        )
        match = find_match(db_session, candidate)
        assert not is_confident_match(match)

    def test_unrelated_company_is_not_merged(self, db_session):
        _seed_company(db_session)
        candidate = DiscoveredCompany(
            company_name="Zenith Renewable Energy Cooperative",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate)
        assert not is_confident_match(match)
        assert match.company is None

    def test_low_confidence_never_auto_merges(self, db_session):
        _seed_company(db_session, website=None, domain=None)
        # Same country, loosely similar name, but not similar enough to merge.
        candidate = DiscoveredCompany(
            company_name="ABC Global Holdings",
            country="United Arab Emirates",
            source="search:mock",
        )
        match = find_match(db_session, candidate)
        assert not is_confident_match(match)
