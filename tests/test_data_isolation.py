"""Every account's saved data is private to it: companies, emails, exports,
search history and scheduled searches, including duplicate detection."""

import asyncio

import pytest

from app.services import saved_search_service

PASSWORD = "correct-horse-battery"
DISCOVER = {"country": "United Arab Emirates", "limit": 10}


def _headers(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def api(unauthenticated_client):
    return unauthenticated_client


@pytest.fixture()
def alice(api):
    return _headers(api, "alice@example.com")


@pytest.fixture()
def bob(api):
    return _headers(api, "bob@example.com")


def _discover(api, headers):
    response = api.post("/api/discover", json=DISCOVER, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["companies"]


def _save_all(api, headers, companies):
    """Save every preview; returns the distinct saved companies. Two previews
    of the same company merge into one record, so this can be shorter than
    `companies`."""
    response = api.post("/api/companies/save-bulk", json={"companies": companies}, headers=headers)
    assert response.status_code == 200, response.text
    distinct = {c["id"]: c for c in response.json()["results"] if c is not None}
    return list(distinct.values())


def _schedule(api, headers):
    response = api.post(
        "/api/saved-searches",
        json={"name": "UAE diesel", "country": "United Arab Emirates", "limit": 10},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestCompaniesAndEmails:
    def test_companies_are_only_listed_for_their_owner(self, api, alice, bob):
        saved = _save_all(api, alice, _discover(api, alice))
        assert saved

        assert api.get("/api/companies", headers=alice).json()["total"] == len(saved)
        assert api.get("/api/companies", headers=bob).json()["total"] == 0

    def test_another_accounts_company_profile_is_not_found(self, api, alice, bob):
        company = _save_all(api, alice, _discover(api, alice))[0]
        assert api.get(f"/api/companies/{company['id']}", headers=alice).status_code == 200
        assert api.get(f"/api/companies/{company['id']}", headers=bob).status_code == 404

    def test_emails_are_private(self, api, alice, bob):
        _save_all(api, alice, _discover(api, alice))
        assert api.get("/api/emails", headers=alice).json()["total"] > 0
        assert api.get("/api/emails", headers=bob).json()["total"] == 0

    @pytest.mark.parametrize("path", ["/api/companies/export", "/api/emails/export"])
    def test_exports_only_contain_your_own_data(self, api, alice, bob, path):
        saved = _save_all(api, alice, _discover(api, alice))
        name = saved[0]["company_name"]

        assert name in api.get(path, headers=alice).text
        assert name not in api.get(path, headers=bob).text

    def test_search_history_is_private(self, api, alice, bob):
        _discover(api, alice)
        assert api.get("/api/searches", headers=alice).json()["total"] == 1
        assert api.get("/api/searches", headers=bob).json()["total"] == 0


class TestDuplicateDetection:
    def test_a_company_saved_by_someone_else_is_new_for_you(self, api, alice, bob):
        alice_saved = _save_all(api, alice, _discover(api, alice))

        # Alice sees her companies as already saved; Bob sees the same
        # results as new — he never saved them.
        assert all(c["already_saved"] for c in _discover(api, alice))
        bob_previews = _discover(api, bob)
        assert not any(c["already_saved"] for c in bob_previews)

        bob_saved = _save_all(api, bob, bob_previews)
        assert len(bob_saved) == len(alice_saved)
        assert {c["id"] for c in bob_saved}.isdisjoint({c["id"] for c in alice_saved})


class TestScheduledSearches:
    def test_saved_searches_are_private(self, api, alice, bob):
        search = _schedule(api, alice)

        assert len(api.get("/api/saved-searches", headers=alice).json()) == 1
        assert api.get("/api/saved-searches", headers=bob).json() == []

        path = f"/api/saved-searches/{search['id']}"
        assert api.patch(path, params={"is_active": False}, headers=bob).status_code == 404
        assert api.delete(path, headers=bob).status_code == 404
        assert len(api.get("/api/saved-searches", headers=alice).json()) == 1

    def test_run_due_only_runs_your_own_searches(self, api, alice, bob):
        _schedule(api, alice)
        assert api.post("/api/saved-searches/run-due", headers=bob).json()["ran"] == 0
        assert api.post("/api/saved-searches/run-due", headers=alice).json()["ran"] == 1

    def test_the_worker_saves_each_searchs_results_for_its_owner(
        self, api, alice, bob, db_session
    ):
        _schedule(api, alice)
        ran = asyncio.run(saved_search_service.run_due_saved_searches(db_session))
        assert ran == 1

        assert api.get("/api/companies", headers=alice).json()["total"] > 0
        assert api.get("/api/companies", headers=bob).json()["total"] == 0
