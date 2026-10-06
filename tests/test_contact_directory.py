"""The shared contact directory: what gets recorded, how a company's address
format is learned, how lookups use both before spending anything, and the
opt-out. No outside service is called — the verifier, DNS and providers are
replaced so each test decides what comes back."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import Settings
from app.database.models import ContactRecord, EmailDomain, SuppressedEmail
from app.discovery import email_finder, email_verification
from app.discovery.email_verification import Verdict
from app.discovery.types import DiscoveredCompany
from app.services import company_service, contact_directory

NO_VERIFIER = Settings(email_guessing_enabled=True)
VERIFIER = Settings(
    email_verify_provider="millionverifier",
    email_verify_api_key="key-not-real",
    email_guessing_enabled=True,
)


def _person(name, *emails, valid=True, domain="gulfstar.example", source="apollo"):
    return DiscoveredCompany(
        company_name="Gulfstar Energy",
        website=f"https://{domain}",
        source=source,
        contact_person_name=name,
        emails=[{"email": e, "is_valid": valid} for e in emails],
    )


def _site(*emails, domain="gulfstar.example"):
    return DiscoveredCompany(
        company_name="Gulfstar Energy",
        website=f"https://{domain}",
        source="search:serper",
        emails=[{"email": e, "is_valid": True} for e in emails],
    )


def _records(db):
    return {r.email: r for r in db.execute(select(ContactRecord)).scalars()}


def _formats(db, domain="gulfstar.example"):
    row = db.get(EmailDomain, domain)
    return row.pattern_counts if row else {}


class _FakeVerifier:
    def __init__(self, answers=None, default=email_verification.UNDELIVERABLE):
        self.answers = answers or {}
        self.default = default
        self.checked = []

    async def verify(self, addresses):
        self.checked.extend(addresses)
        return {
            a: self.answers.get(a, Verdict(self.default, "mailbox_not_found")) for a in addresses
        }


@pytest.fixture()
def verifier(monkeypatch):
    def install(answers=None, **kwargs):
        fake = _FakeVerifier(answers, **kwargs)
        monkeypatch.setattr(email_verification, "get_provider", lambda settings: fake)

        async def mx_ok(email, **kw):
            return True

        monkeypatch.setattr(email_finder, "validate_email_domain", mx_ok)
        return fake

    return install


@pytest.fixture()
def no_provider(monkeypatch):
    """The paid contact provider must not be reached."""

    async def refuse(**kwargs):
        raise AssertionError("the paid provider was called")

    monkeypatch.setattr(company_service, "find_person_email", refuse)


@pytest.fixture()
def provider_finds_nothing(monkeypatch):
    async def nothing(**kwargs):
        return None

    monkeypatch.setattr(company_service, "find_person_email", nothing)


def _confirmed(address):
    return {address: Verdict(email_verification.DELIVERABLE, "mailbox_confirmed")}


class TestRecording:
    def test_a_persons_address_is_stored_with_their_name_and_teaches_the_format(self, db_session):
        contact_directory.record_candidates(
            db_session, [_person("Jane Doe", "Jane.Doe@Gulfstar.example")]
        )
        record = _records(db_session)["jane.doe@gulfstar.example"]
        assert record.full_name == "Jane Doe"
        assert record.name_key == "jane doe"
        assert record.domain == "gulfstar.example"
        assert record.source == "apollo"
        assert _formats(db_session) == {"{first}.{last}": 1}

    def test_an_address_that_isnt_theirs_gets_no_name(self, db_session):
        contact_directory.record_candidates(
            db_session, [_person("Jane Doe", "info@gulfstar.example")]
        )
        record = _records(db_session)["info@gulfstar.example"]
        assert record.full_name is None and record.name_key is None
        assert _formats(db_session) == {}

    def test_website_addresses_teach_the_format_but_role_addresses_dont(self, db_session):
        contact_directory.record_candidates(
            db_session,
            [
                _site(
                    "omar.haddad@gulfstar.example",
                    "sales.team@gulfstar.example",
                    "info@gulfstar.example",
                )
            ],
        )
        assert set(_records(db_session)) == {
            "omar.haddad@gulfstar.example",
            "sales.team@gulfstar.example",
            "info@gulfstar.example",
        }
        assert _formats(db_session) == {"{first}.{last}": 1}

    def test_one_batch_with_repeats_and_shared_domains_is_all_kept(self, db_session):
        contact_directory.record_candidates(
            db_session,
            [
                _person("Jane Doe", "jane.doe@gulfstar.example"),
                _person("Omar Haddad", "omar.haddad@gulfstar.example"),
                _site("jane.doe@gulfstar.example", "info@gulfstar.example"),
            ],
        )
        records = _records(db_session)
        assert set(records) == {
            "jane.doe@gulfstar.example",
            "omar.haddad@gulfstar.example",
            "info@gulfstar.example",
        }
        assert records["jane.doe@gulfstar.example"].times_seen == 2
        assert _formats(db_session) == {"{first}.{last}": 2}

    def test_seeing_an_address_again_is_not_new_evidence(self, db_session):
        for _ in range(3):
            contact_directory.record_candidates(
                db_session, [_person("Jane Doe", "jane.doe@gulfstar.example")]
            )
        assert _records(db_session)["jane.doe@gulfstar.example"].times_seen == 3
        assert _formats(db_session) == {"{first}.{last}": 1}

    def test_mock_invalid_and_opted_out_addresses_are_not_stored(self, db_session):
        mock = _site("fake@gulfstar.example")
        mock.is_mock = True
        contact_directory.suppress(db_session, "gone@gulfstar.example")
        contact_directory.record_candidates(
            db_session,
            [
                mock,
                _person("Jane Doe", "jane.doe@gulfstar.example", valid=False),
                _site("gone@gulfstar.example"),
            ],
        )
        assert _records(db_session) == {}


class TestPersonLookup:
    async def test_a_known_person_costs_nothing(self, db_session, verifier, no_provider):
        fake = verifier()
        contact_directory.record_candidates(
            db_session, [_person("Jane Doe", "jane.doe@gulfstar.example")]
        )
        found = await company_service._find_person_email(
            db_session, VERIFIER, domain="gulfstar.example", full_name="Dr. Jane Doe"
        )
        assert found == {"email": "jane.doe@gulfstar.example", "is_valid": True}
        assert fake.checked == []

    async def test_a_known_format_needs_one_check(self, db_session, verifier, no_provider):
        contact_directory.record_candidates(
            db_session, [_person("Jane Doe", "jane.doe@gulfstar.example")]
        )
        fake = verifier(_confirmed("john.smith@gulfstar.example"))
        found = await company_service._find_person_email(
            db_session, VERIFIER, domain="gulfstar.example", full_name="John Smith"
        )
        assert found == {"email": "john.smith@gulfstar.example", "is_valid": True}
        # A catch-all probe, then the one address in the known format.
        assert len(fake.checked) == 2
        assert fake.checked[1] == "john.smith@gulfstar.example"

    async def test_catch_all_answer_is_remembered(self, db_session, verifier, monkeypatch):
        async def nothing(**kwargs):
            return None

        monkeypatch.setattr(company_service, "find_person_email", nothing)
        fake = verifier(default=email_verification.RISKY)  # accepts everything
        await company_service._find_person_email(
            db_session, VERIFIER, domain="gulfstar.example", full_name="John Smith"
        )
        assert db_session.get(EmailDomain, "gulfstar.example").is_catch_all is True
        checks_first_time = len(fake.checked)

        await company_service._find_person_email(
            db_session, VERIFIER, domain="gulfstar.example", full_name="Mary Major"
        )
        assert len(fake.checked) == checks_first_time  # no second probe

    async def test_a_failed_targeted_check_is_not_repeated(self, db_session, verifier, monkeypatch):
        async def nothing(**kwargs):
            return None

        monkeypatch.setattr(company_service, "find_person_email", nothing)
        contact_directory.record_candidates(
            db_session, [_person("Jane Doe", "jane.doe@gulfstar.example")]
        )
        fake = verifier(_confirmed("jsmith@gulfstar.example"))
        found = await company_service._find_person_email(
            db_session, VERIFIER, domain="gulfstar.example", full_name="John Smith"
        )
        assert found == {"email": "jsmith@gulfstar.example", "is_valid": True}
        assert fake.checked.count("john.smith@gulfstar.example") == 1

    async def test_well_evidenced_format_is_offered_unconfirmed_without_a_verifier(
        self, db_session, provider_finds_nothing
    ):
        contact_directory.record_candidates(
            db_session,
            [
                _person("Jane Doe", "jane.doe@gulfstar.example"),
                _person("Omar Haddad", "omar.haddad@gulfstar.example"),
            ],
        )
        found = await company_service._find_person_email(
            db_session, NO_VERIFIER, domain="gulfstar.example", full_name="John Smith"
        )
        assert found == {"email": "john.smith@gulfstar.example", "is_valid": None}

    async def test_one_example_is_not_enough_to_offer_a_format(
        self, db_session, provider_finds_nothing
    ):
        contact_directory.record_candidates(
            db_session, [_person("Jane Doe", "jane.doe@gulfstar.example")]
        )
        found = await company_service._find_person_email(
            db_session, NO_VERIFIER, domain="gulfstar.example", full_name="John Smith"
        )
        assert found is None

    async def test_a_format_the_verifier_rejected_is_not_offered(
        self, db_session, verifier, monkeypatch
    ):
        async def nothing(**kwargs):
            return None

        monkeypatch.setattr(company_service, "find_person_email", nothing)
        contact_directory.record_candidates(
            db_session,
            [
                _person("Jane Doe", "jane.doe@gulfstar.example"),
                _person("Omar Haddad", "omar.haddad@gulfstar.example"),
            ],
        )
        verifier()  # every mailbox comes back as not existing
        found = await company_service._find_person_email(
            db_session, VERIFIER, domain="gulfstar.example", full_name="John Smith"
        )
        assert found is None


class TestCompanySearch:
    async def test_known_addresses_fill_a_company_with_none(self, db_session):
        contact_directory.record_candidates(db_session, [_site("info@gulfstar.example")])
        later = DiscoveredCompany(
            company_name="Gulfstar Energy", website="https://www.gulfstar.example"
        )
        await company_service._fill_missing_emails(db_session, [later])
        assert later.emails == [{"email": "info@gulfstar.example", "is_valid": True}]


class TestOptOut:
    def test_opt_out_removes_and_blocks(self, unauthenticated_client, db_session):
        contact_directory.record_candidates(db_session, [_site("jane.doe@gulfstar.example")])
        response = unauthenticated_client.post(
            "/api/privacy/opt-out", json={"email": "Jane.Doe@gulfstar.example"}
        )
        assert response.status_code == 202
        assert _records(db_session) == {}
        assert db_session.execute(select(SuppressedEmail)).scalars().one().email == (
            "jane.doe@gulfstar.example"
        )

        contact_directory.record_candidates(db_session, [_site("jane.doe@gulfstar.example")])
        assert _records(db_session) == {}

    def test_same_answer_for_an_unknown_address(self, unauthenticated_client):
        first = unauthenticated_client.post(
            "/api/privacy/opt-out", json={"email": "nobody@example.org"}
        )
        again = unauthenticated_client.post(
            "/api/privacy/opt-out", json={"email": "nobody@example.org"}
        )
        assert first.status_code == again.status_code == 202
        assert first.json() == again.json()

    def test_a_suppressed_address_is_not_offered_from_a_format(self, db_session):
        contact_directory.record_candidates(
            db_session,
            [
                _person("Jane Doe", "jane.doe@gulfstar.example"),
                _person("Omar Haddad", "omar.haddad@gulfstar.example"),
            ],
        )
        contact_directory.suppress(db_session, "john.smith@gulfstar.example")
        assert (
            contact_directory.pattern_email(
                db_session, domain="gulfstar.example", full_name="John Smith"
            )
            is None
        )


class TestCustomersOwnListsStayPrivate:
    def test_verifying_a_pasted_list_records_nothing(self, client, db_session):
        response = client.post("/api/emails/verify", json={"emails": ["jane.doe@gulfstar.example"]})
        assert response.status_code == 200, response.text
        assert _records(db_session) == {}
