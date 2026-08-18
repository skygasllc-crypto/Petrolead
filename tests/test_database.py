from app.database.models import (
    Company,
    CompanyContact,
    CompanySource,
    SearchQuery,
    SearchStatus,
    SocialProfile,
)
from app.discovery.normalizer import normalize_company_name


class TestCompanyModel:
    def test_create_and_read_company(self, db_session):
        company = Company(
            company_name="Falcon Oil Trading LLC",
            normalized_name=normalize_company_name("Falcon Oil Trading LLC"),
            country="United Arab Emirates",
            city="Dubai",
            region="Middle East",
            website="https://falconoil.example",
            domain="falconoil.example",
            industry="Petroleum Trading",
            description="A regional fuel trading company.",
            activities=["trading"],
            products=["EN590", "Diesel"],
            keywords=["diesel", "fuel"],
            source="search:mock",
            source_url="https://falconoil.example",
            relevance_score=75,
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)

        assert company.id is not None
        fetched = db_session.get(Company, company.id)
        assert fetched is not None
        assert fetched.company_name == "Falcon Oil Trading LLC"
        assert fetched.products == ["EN590", "Diesel"]
        assert fetched.relevance_score == 75

    def test_company_source_relationship(self, db_session):
        company = Company(
            company_name="Falcon Oil Trading LLC",
            normalized_name=normalize_company_name("Falcon Oil Trading LLC"),
            relevance_score=50,
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)

        source = CompanySource(
            company_id=company.id,
            source="search:mock",
            source_url="https://falconoil.example",
            raw_company_name="Falcon Oil Trading LLC",
            match_confidence=1.0,
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(company)

        assert len(company.sources) == 1
        assert company.sources[0].source == "search:mock"

    def test_company_contact_relationship(self, db_session):
        company = Company(
            company_name="Falcon Oil Trading LLC",
            normalized_name=normalize_company_name("Falcon Oil Trading LLC"),
            relevance_score=50,
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)

        company.contact = CompanyContact(contact_page_url="https://falconoil.example/contact")
        db_session.commit()
        db_session.refresh(company)

        assert company.contact.contact_page_url == "https://falconoil.example/contact"

    def test_social_profile_relationship(self, db_session):
        company = Company(
            company_name="Falcon Oil Trading LLC",
            normalized_name=normalize_company_name("Falcon Oil Trading LLC"),
            relevance_score=50,
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)

        company.social_profiles.append(
            SocialProfile(platform="linkedin", url="https://linkedin.com/company/falconoil")
        )
        db_session.commit()
        db_session.refresh(company)

        assert len(company.social_profiles) == 1
        assert company.social_profiles[0].platform == "linkedin"


class TestSearchQueryModel:
    def test_create_search_query(self, db_session):
        search = SearchQuery(
            region="Middle East",
            country="United Arab Emirates",
            industry="Petroleum Trading",
            keywords=["diesel"],
            result_limit=25,
            status=SearchStatus.PENDING,
        )
        db_session.add(search)
        db_session.commit()
        db_session.refresh(search)

        assert search.id is not None
        assert search.status == SearchStatus.PENDING
        fetched = db_session.get(SearchQuery, search.id)
        assert fetched.keywords == ["diesel"]
