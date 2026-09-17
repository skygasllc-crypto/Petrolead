"""Tests for plans, email credits and usage limits.

conftest switches BILLING_ENFORCED off for the rest of the suite; these tests
turn it back on by patching `billing_service.get_settings` (and
`auth.get_settings`, so ADMIN_EMAILS grants the admin account) with a copy of
the real settings — JWT signing stays consistent with the rest of the app.
"""

import asyncio
from datetime import timedelta

import pytest
from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from app.api import auth as auth_module
from app.config import get_settings as real_get_settings
from app.database.models import CreditTransaction, Subscription, utcnow
from app.discovery import email_verification as verification
from app.discovery import emails as emails_module
from app.discovery import extractor as extractor_module
from app.discovery.types import DiscoveredCompany
from app.services import billing_service, company_service, saved_search_service
from tests.test_url_lookup import _fake_fetch_page, _FakeRealProvider

PASSWORD = "correct-horse-battery"
ADMIN_EMAIL = "admin@example.com"
PROFILE_URL = "https://linkedin.com/in/michaeljones"


@pytest.fixture(autouse=True)
def enforce_billing(monkeypatch):
    settings = real_get_settings().model_copy(
        update={"billing_enforced": True, "admin_emails": ADMIN_EMAIL}
    )
    monkeypatch.setattr(billing_service, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)


def _register(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture()
def api(unauthenticated_client):
    return unauthenticated_client


@pytest.fixture()
def admin(api):
    return _register(api, ADMIN_EMAIL)[1]


@pytest.fixture()
def member(api):
    """(user_id, headers) for a regular account."""
    return _register(api, "member@example.com")


def _assign(api, admin, user_id, plan, credits):
    response = api.put(
        f"/api/admin/users/{user_id}/subscription",
        json={"plan": plan, "credits_per_month": credits},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _adjust(api, admin, user_id, amount):
    response = api.post(
        f"/api/admin/users/{user_id}/credits", json={"amount": amount}, headers=admin
    )
    assert response.status_code == 200, response.text
    return response.json()


def _billing(api, headers):
    return api.get("/api/billing/me", headers=headers).json()


def _fake_person_lookups(monkeypatch, emails_for=lambda full_name: True):
    """Real (non-mock) lookups against a fake provider — `emails_for(name)`
    decides whether Hunter "finds" an email for that person."""
    provider = _FakeRealProvider(
        snippet_title=(
            "Michael Jones - Senior Trading Manager at Falcon Petroleum Trading | LinkedIn"
        ),
        website_url="https://falconpetro.example/about",
    )
    monkeypatch.setattr(company_service, "get_search_provider", lambda settings: provider)

    async def fake_find_person_email(*, domain, full_name, settings):
        if not emails_for(full_name):
            return None
        slug = full_name.lower().replace(" ", ".")
        return {"email": f"{slug}@{domain}", "is_valid": True}

    monkeypatch.setattr(company_service, "find_person_email", fake_find_person_email)


def _fake_search_results(monkeypatch, *, with_emails: int, without_emails: int):
    """Make a company search return results whose emails we control — the
    mock provider never enriches candidates, so it finds none by itself.

    Returns the list the fake source appends to on each call, so a test can
    tell whether the search ran at all."""
    companies = [
        DiscoveredCompany(
            company_name=f"Emailed Petroleum {i}",
            website=f"https://emailed{i}.example",
            emails=[{"email": f"info@emailed{i}.example", "is_valid": True}],
        )
        for i in range(with_emails)
    ] + [
        DiscoveredCompany(company_name=f"Quiet Petroleum {i}", website=f"https://quiet{i}.example")
        for i in range(without_emails)
    ]
    calls = []

    class FakeSource:
        async def discover(self, request):
            calls.append(request)
            return list(companies)

    monkeypatch.setattr(company_service, "SearchSource", FakeSource)
    return calls


def _subscription(db_session, user_id):
    db_session.expire_all()
    return db_session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one()


class TestNoPlan:
    def test_new_account_starts_without_a_plan(self, api, member):
        billing = _billing(api, member[1])
        assert billing["plan"] is None
        assert billing["credits_balance"] == 0
        assert billing["exempt"] is False

    def test_tools_are_blocked_without_a_plan(self, api, member):
        headers = member[1]
        lookup = api.post("/api/discover-url", json={"url": PROFILE_URL}, headers=headers)
        assert lookup.status_code == 402
        assert "active plan" in lookup.json()["detail"]

        verify = api.post("/api/emails/verify", json={"emails": ["a@b.co"]}, headers=headers)
        assert verify.status_code == 402

        discover = api.post("/api/discover", json={"limit": 10}, headers=headers)
        assert discover.status_code == 402

    def test_admins_are_never_limited(self, api, admin):
        assert _billing(api, admin)["exempt"] is True
        response = api.post("/api/discover-url", json={"url": PROFILE_URL}, headers=admin)
        assert response.status_code == 200


class TestAdminPlanManagement:
    def test_assigning_a_plan_grants_the_first_months_credits(self, api, admin, member, db_session):
        body = _assign(api, admin, member[0], "basic", 1000)
        assert body["subscription"]["plan"] == "basic"
        assert body["subscription"]["credits_balance"] == 1000

        billing = _billing(api, member[1])
        assert billing["plan_name"] == "Basic"
        assert billing["credits_balance"] == 1000
        assert billing["export"] is False

        reasons = db_session.execute(select(CreditTransaction.reason)).scalars().all()
        assert "plan_started" in reasons

    def test_changing_plan_keeps_the_balance(self, api, admin, member):
        _assign(api, admin, member[0], "basic", 1000)
        body = _assign(api, admin, member[0], "professional", 5000)
        assert body["subscription"]["plan"] == "professional"
        assert body["subscription"]["credits_per_month"] == 5000
        assert body["subscription"]["credits_balance"] == 1000

    @pytest.mark.parametrize(("plan", "credits"), [("professional", 1000), ("gold", 1000)])
    def test_rejects_unknown_plans_and_tiers(self, api, admin, member, plan, credits):
        response = api.put(
            f"/api/admin/users/{member[0]}/subscription",
            json={"plan": plan, "credits_per_month": credits},
            headers=admin,
        )
        assert response.status_code == 422

    def test_only_admins_can_manage_plans(self, api, member):
        response = api.put(
            f"/api/admin/users/{member[0]}/subscription",
            json={"plan": "basic", "credits_per_month": 1000},
            headers=member[1],
        )
        assert response.status_code == 403

    def test_adjusting_credits_never_goes_below_zero(self, api, admin, member):
        _assign(api, admin, member[0], "basic", 1000)
        assert _adjust(api, admin, member[0], 500)["subscription"]["credits_balance"] == 1500
        assert _adjust(api, admin, member[0], -5000)["subscription"]["credits_balance"] == 0

    def test_adjusting_credits_needs_a_plan(self, api, admin, member):
        response = api.post(
            f"/api/admin/users/{member[0]}/credits", json={"amount": 100}, headers=admin
        )
        assert response.status_code == 422

    def test_removing_a_plan_blocks_the_account_again(self, api, admin, member):
        _assign(api, admin, member[0], "basic", 1000)
        response = api.delete(f"/api/admin/users/{member[0]}/subscription", headers=admin)
        assert response.status_code == 200
        assert response.json()["subscription"] is None
        lookup = api.post("/api/discover-url", json={"url": PROFILE_URL}, headers=member[1])
        assert lookup.status_code == 402

    def test_user_list_shows_each_plan(self, api, admin, member):
        _assign(api, admin, member[0], "enterprise", 50000)
        users = {u["email"]: u for u in api.get("/api/admin/users", headers=admin).json()}
        assert users["member@example.com"]["subscription"]["credits_balance"] == 50000
        assert users[ADMIN_EMAIL]["subscription"] is None


class TestEmailCredits:
    def test_a_found_email_spends_one_credit(self, api, admin, member, monkeypatch, db_session):
        _fake_person_lookups(monkeypatch)
        _assign(api, admin, member[0], "basic", 1000)

        response = api.post("/api/discover-url", json={"url": PROFILE_URL}, headers=member[1])
        assert response.status_code == 200
        assert response.json()["emails"]
        assert _billing(api, member[1])["credits_balance"] == 999

        spent = db_session.execute(
            select(CreditTransaction).where(CreditTransaction.reason == "email_found")
        ).scalar_one()
        assert spent.delta == -1
        assert spent.balance_after == 999

    def test_no_email_found_spends_nothing(self, api, admin, member, monkeypatch):
        _fake_person_lookups(monkeypatch, emails_for=lambda name: False)
        _assign(api, admin, member[0], "basic", 1000)

        response = api.post("/api/discover-url", json={"url": PROFILE_URL}, headers=member[1])
        assert response.status_code == 422
        assert _billing(api, member[1])["credits_balance"] == 1000

    def test_website_extraction_is_free(self, api, admin, member, monkeypatch):
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page)
        _assign(api, admin, member[0], "basic", 1000)

        response = api.post(
            "/api/discover-url", json={"url": "https://falconpetro.example"}, headers=member[1]
        )
        assert response.status_code == 200
        assert response.json()["emails"]
        assert _billing(api, member[1])["credits_balance"] == 1000

    def test_out_of_credits_is_blocked_before_any_lookup_runs(
        self, api, admin, member, monkeypatch
    ):
        class ExplodingProvider:
            name = "exploding"

            async def search(self, query, *, limit=10):
                raise AssertionError("no lookup should run without credits")

        monkeypatch.setattr(company_service, "get_search_provider", lambda s: ExplodingProvider())
        _assign(api, admin, member[0], "basic", 1000)
        _adjust(api, admin, member[0], -1000)

        response = api.post("/api/discover-url", json={"url": PROFILE_URL}, headers=member[1])
        assert response.status_code == 402
        assert "out of email credits" in response.json()["detail"]

    def test_single_name_and_company_lookup_works_on_basic(self, api, admin, member, monkeypatch):
        _fake_person_lookups(monkeypatch)
        _assign(api, admin, member[0], "basic", 1000)

        response = api.post(
            "/api/contacts/bulk-lookup",
            json={"items": [{"full_name": "Jane Doe", "company_name": "Falcon Petroleum"}]},
            headers=member[1],
        )
        assert response.status_code == 200
        assert response.json()["succeeded_count"] == 1
        assert _billing(api, member[1])["credits_balance"] == 999

    def test_bulk_lookup_needs_professional(self, api, admin, member):
        _assign(api, admin, member[0], "basic", 1000)
        items = [
            {"full_name": "Jane Doe", "company_name": "Falcon Petroleum"},
            {"full_name": "John Roe", "company_name": "Falcon Petroleum"},
        ]
        response = api.post("/api/contacts/bulk-lookup", json={"items": items}, headers=member[1])
        assert response.status_code == 403
        assert "Bulk lookup isn't included in the Basic plan" in response.json()["detail"]

    def test_bulk_lookup_only_charges_for_found_emails(self, api, admin, member, monkeypatch):
        _fake_person_lookups(monkeypatch, emails_for=lambda name: name == "Jane Doe")
        _assign(api, admin, member[0], "professional", 2000)
        items = [
            {"full_name": name, "company_name": "Falcon Petroleum"}
            for name in ("Jane Doe", "John Roe", "Amy Poe")
        ]
        response = api.post("/api/contacts/bulk-lookup", json={"items": items}, headers=member[1])
        assert response.status_code == 200
        assert response.json()["succeeded_count"] == 1
        assert _billing(api, member[1])["credits_balance"] == 1999

    def test_bulk_lookup_needs_a_credit_for_every_line(self, api, admin, member):
        _assign(api, admin, member[0], "professional", 2000)
        _adjust(api, admin, member[0], -1998)
        items = [
            {"full_name": name, "company_name": "Falcon Petroleum"}
            for name in ("Jane Doe", "John Roe", "Amy Poe")
        ]
        response = api.post("/api/contacts/bulk-lookup", json={"items": items}, headers=member[1])
        assert response.status_code == 402
        assert "needs up to 3 email credits, but you have 2" in response.json()["detail"]


class TestSearchCredits:
    """A company search costs one credit per result that carries an email."""

    def test_each_result_with_an_email_spends_a_credit(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "professional", 2000)
        _fake_search_results(monkeypatch, with_emails=2, without_emails=1)

        response = api.post("/api/discover", json={"limit": 10}, headers=member[1])
        assert response.status_code == 200, response.text
        assert len(response.json()["companies"]) == 3
        assert _billing(api, member[1])["credits_balance"] == 1998

    def test_results_without_an_email_are_free(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "professional", 2000)
        _fake_search_results(monkeypatch, with_emails=0, without_emails=3)

        assert api.post("/api/discover", json={"limit": 10}, headers=member[1]).status_code == 200
        assert _billing(api, member[1])["credits_balance"] == 2000

    def test_the_spend_is_recorded_in_the_ledger(self, api, admin, member, monkeypatch, db_session):
        _assign(api, admin, member[0], "professional", 2000)
        _fake_search_results(monkeypatch, with_emails=2, without_emails=1)
        api.post("/api/discover", json={"limit": 10}, headers=member[1])

        entry = db_session.execute(
            select(CreditTransaction).where(CreditTransaction.reason == "email_found")
        ).scalar_one()
        assert entry.delta == -2
        assert entry.balance_after == 1998
        assert "2 of 3 results with an email" in entry.detail

    def test_a_search_needs_a_credit_before_it_runs(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "professional", 2000)
        _adjust(api, admin, member[0], -2000)
        calls = _fake_search_results(monkeypatch, with_emails=2, without_emails=1)

        response = api.post("/api/discover", json={"limit": 10}, headers=member[1])
        assert response.status_code == 402
        assert "out of email credits" in response.json()["detail"]
        # The provider is never called, so an empty balance can't cost money.
        assert calls == []

    def test_a_search_spends_no_more_than_the_balance(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "professional", 2000)
        _adjust(api, admin, member[0], -1999)
        _fake_search_results(monkeypatch, with_emails=3, without_emails=0)

        assert api.post("/api/discover", json={"limit": 10}, headers=member[1]).status_code == 200
        assert _billing(api, member[1])["credits_balance"] == 0


def _fake_mx(results_by_domain):
    """Answer MX lookups from a table, so these never touch real DNS."""

    async def fake_validate_email_domain(email, *, timeout=3.0):
        return results_by_domain[email.rsplit("@", 1)[-1]]

    return fake_validate_email_domain


class TestVerificationCredits:
    """One credit per mailbox a provider actually confirms.

    The first test is the important one: with no provider configured —
    the default, and the live configuration — verification must stay free.
    Charging there would bill customers for a DNS lookup that costs nothing.
    """

    @staticmethod
    def _provider(monkeypatch, verdicts_by_address):
        class FakeProvider:
            async def verify(self, addresses):
                return {a: verdicts_by_address[a] for a in addresses}

        monkeypatch.setattr(verification, "get_provider", lambda settings: FakeProvider())

    def test_without_a_provider_verification_is_free(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "basic", 1000)
        monkeypatch.setattr(
            emails_module, "validate_email_domain", _fake_mx({"gulfstar.example": True})
        )

        response = api.post(
            "/api/emails/verify",
            json={"emails": ["jane@gulfstar.example", "bob@gulfstar.example"]},
            headers=member[1],
        )
        assert response.status_code == 200
        assert _billing(api, member[1])["credits_balance"] == 1000

    def test_one_credit_per_confirmed_mailbox(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "basic", 1000)
        self._provider(
            monkeypatch,
            {
                "jane@gulfstar.example": verification.Verdict(
                    verification.DELIVERABLE, "mailbox_confirmed"
                ),
                "bob@gulfstar.example": verification.Verdict(
                    verification.UNDELIVERABLE, "mailbox_not_found"
                ),
            },
        )

        response = api.post(
            "/api/emails/verify",
            json={"emails": ["jane@gulfstar.example", "bob@gulfstar.example"]},
            headers=member[1],
        )
        assert response.status_code == 200
        # Both were answered — a rejection is as valuable as a confirmation.
        assert _billing(api, member[1])["credits_balance"] == 998

    def test_locally_screened_addresses_are_free(self, api, admin, member, monkeypatch):
        """A typo or throwaway domain never reaches the provider, so it
        costs us nothing and must cost the customer nothing."""
        _assign(api, admin, member[0], "basic", 1000)
        self._provider(monkeypatch, {})

        response = api.post(
            "/api/emails/verify",
            json={"emails": ["someone@mailinator.com", "jane@gmial.com", "not-an-email"]},
            headers=member[1],
        )
        assert response.status_code == 200
        assert _billing(api, member[1])["credits_balance"] == 1000

    def test_a_failed_provider_call_is_not_charged(self, api, admin, member, monkeypatch):
        _assign(api, admin, member[0], "basic", 1000)
        self._provider(
            monkeypatch,
            {
                "jane@gulfstar.example": verification.Verdict(
                    verification.UNKNOWN, "provider_error"
                )
            },
        )
        monkeypatch.setattr(
            emails_module, "validate_email_domain", _fake_mx({"gulfstar.example": True})
        )

        response = api.post(
            "/api/emails/verify",
            json={"emails": ["jane@gulfstar.example"]},
            headers=member[1],
        )
        assert response.status_code == 200
        assert _billing(api, member[1])["credits_balance"] == 1000

    def test_an_empty_balance_is_refused_before_the_provider_runs(
        self, api, admin, member, monkeypatch
    ):
        _assign(api, admin, member[0], "basic", 1000)
        _adjust(api, admin, member[0], -1000)
        called = []

        class FakeProvider:
            async def verify(self, addresses):
                called.append(addresses)
                return {}

        monkeypatch.setattr(verification, "get_provider", lambda settings: FakeProvider())

        response = api.post(
            "/api/emails/verify",
            json={"emails": ["jane@gulfstar.example"]},
            headers=member[1],
        )
        assert response.status_code == 402
        assert called == [], "an empty balance must not ring up provider fees"


class TestPlanLimits:
    def test_results_per_search_are_capped_by_plan(self, api, admin, member):
        _assign(api, admin, member[0], "basic", 1000)
        response = api.post("/api/discover", json={"limit": 25}, headers=member[1])
        assert response.status_code == 403
        assert "up to 10 results" in response.json()["detail"]

    def test_daily_discovery_limit(self, api, admin, member, db_session):
        _assign(api, admin, member[0], "basic", 1000)
        for _ in range(5):
            response = api.post("/api/discover", json={"limit": 10}, headers=member[1])
            assert response.status_code == 200
        assert _billing(api, member[1])["discovery_searches_today"] == 5

        sixth = api.post("/api/discover", json={"limit": 10}, headers=member[1])
        assert sixth.status_code == 429

        subscription = _subscription(db_session, member[0])
        subscription.discovery_day = (utcnow() - timedelta(days=1)).date().isoformat()
        db_session.commit()
        assert api.post("/api/discover", json={"limit": 10}, headers=member[1]).status_code == 200
        assert _billing(api, member[1])["discovery_searches_today"] == 1

    @pytest.mark.parametrize("path", ["/api/companies/export", "/api/emails/export"])
    def test_exports_need_professional(self, api, admin, member, path):
        _assign(api, admin, member[0], "basic", 1000)
        assert api.get(path, headers=member[1]).status_code == 403

        _assign(api, admin, member[0], "professional", 2000)
        assert api.get(path, headers=member[1]).status_code == 200

    def test_email_verifier_is_included_in_basic(self, api, admin, member, monkeypatch):
        async def fake_mx(email, *, timeout=3.0):
            return True

        monkeypatch.setattr(emails_module, "validate_email_domain", fake_mx)
        _assign(api, admin, member[0], "basic", 1000)
        response = api.post(
            "/api/emails/verify", json={"emails": ["jane@gulfstar.example"]}, headers=member[1]
        )
        assert response.status_code == 200
        assert _billing(api, member[1])["credits_balance"] == 1000


class TestMonthlyRenewal:
    def test_renewal_adds_credits_and_unused_ones_roll_over(self, api, admin, member, db_session):
        _assign(api, admin, member[0], "basic", 1000)
        subscription = _subscription(db_session, member[0])
        subscription.credits_balance = 400
        subscription.renews_at = utcnow() - timedelta(days=1)
        db_session.commit()

        billing = _billing(api, member[1])
        assert billing["credits_balance"] == 1400
        assert _subscription(db_session, member[0]).renews_at > utcnow()

    def test_every_missed_month_is_granted(self, api, admin, member, db_session):
        _assign(api, admin, member[0], "basic", 1000)
        subscription = _subscription(db_session, member[0])
        subscription.credits_balance = 0
        subscription.renews_at = utcnow() - relativedelta(months=2, days=1)
        db_session.commit()

        assert _billing(api, member[1])["credits_balance"] == 3000
        renewals = db_session.execute(
            select(CreditTransaction).where(CreditTransaction.reason == "monthly_renewal")
        ).scalars().all()
        assert len(renewals) == 3


class TestScheduledSearchLimits:
    @staticmethod
    def _schedule(api, headers, name="UAE diesel"):
        return api.post(
            "/api/saved-searches",
            json={"name": name, "country": "United Arab Emirates", "limit": 10},
            headers=headers,
        )

    def test_basic_has_no_scheduled_searches(self, api, admin, member):
        _assign(api, admin, member[0], "basic", 1000)
        response = self._schedule(api, member[1])
        assert response.status_code == 403
        assert "aren't included in the Basic plan" in response.json()["detail"]
        assert _billing(api, member[1])["scheduled_searches"] == 0

    def test_professional_allows_five(self, api, admin, member):
        _assign(api, admin, member[0], "professional", 2000)
        assert _billing(api, member[1])["scheduled_searches"] == 5
        for i in range(5):
            assert self._schedule(api, member[1], name=f"Search {i}").status_code == 200

        sixth = self._schedule(api, member[1], name="One too many")
        assert sixth.status_code == 403
        assert "up to 5 scheduled searches" in sixth.json()["detail"]

    def test_enterprise_is_unlimited(self, api, admin, member):
        _assign(api, admin, member[0], "enterprise", 50000)
        assert _billing(api, member[1])["scheduled_searches"] is None
        for i in range(6):
            assert self._schedule(api, member[1], name=f"Search {i}").status_code == 200

    def test_scheduled_searches_stop_running_when_the_plan_is_removed(
        self, api, admin, member, db_session
    ):
        _assign(api, admin, member[0], "professional", 2000)
        assert self._schedule(api, member[1]).status_code == 200
        api.delete(f"/api/admin/users/{member[0]}/subscription", headers=admin)

        ran = asyncio.run(saved_search_service.run_due_saved_searches(db_session))
        assert ran == 0

    def test_a_scheduled_run_spends_its_owners_credits(
        self, api, admin, member, db_session, monkeypatch
    ):
        _assign(api, admin, member[0], "professional", 2000)
        assert self._schedule(api, member[1]).status_code == 200
        _fake_search_results(monkeypatch, with_emails=2, without_emails=1)

        assert asyncio.run(saved_search_service.run_due_saved_searches(db_session)) == 1
        assert _billing(api, member[1])["credits_balance"] == 1998

    def test_scheduled_runs_stop_when_the_owner_runs_out_of_credits(
        self, api, admin, member, db_session, monkeypatch
    ):
        _assign(api, admin, member[0], "professional", 2000)
        assert self._schedule(api, member[1]).status_code == 200
        _adjust(api, admin, member[0], -2000)
        calls = _fake_search_results(monkeypatch, with_emails=2, without_emails=1)

        assert asyncio.run(saved_search_service.run_due_saved_searches(db_session)) == 0
        assert calls == []
