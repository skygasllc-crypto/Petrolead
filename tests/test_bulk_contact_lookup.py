"""Tests for POST /api/contacts/bulk-lookup — look up several people at
once, each item either a LinkedIn profile URL or a name+company pair.
"""

from app.discovery import extractor as extractor_module
from app.services import company_service
from tests.test_url_lookup import _fake_fetch_page_unreachable, _FakeRealProvider


class TestBulkContactLookupValidation:
    def test_rejects_empty_items_list(self, client):
        response = client.post("/api/contacts/bulk-lookup", json={"items": []})
        assert response.status_code == 422

    def test_rejects_item_with_neither_form(self, client):
        response = client.post("/api/contacts/bulk-lookup", json={"items": [{}]})
        assert response.status_code == 422

    def test_rejects_item_with_both_forms(self, client):
        response = client.post(
            "/api/contacts/bulk-lookup",
            json={
                "items": [
                    {
                        "url": "https://linkedin.com/in/janedoe",
                        "full_name": "Jane Doe",
                        "company_name": "Falcon Petroleum",
                    }
                ]
            },
        )
        assert response.status_code == 422

    def test_rejects_more_than_max_items(self, client):
        items = [
            {"full_name": f"Person {i}", "company_name": "Falcon Petroleum"} for i in range(26)
        ]
        response = client.post("/api/contacts/bulk-lookup", json={"items": items})
        assert response.status_code == 422


class TestBulkContactLookupUrls:
    def test_looks_up_multiple_urls_independently_in_order(self, client):
        response = client.post(
            "/api/contacts/bulk-lookup",
            json={
                "items": [
                    {"url": "https://linkedin.com/in/personone"},
                    {"url": "https://linkedin.com/in/persontwo"},
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["succeeded_count"] == 2
        assert body["failed_count"] == 0
        assert len(body["results"]) == 2
        assert body["results"][0]["input_url"] == "https://linkedin.com/in/personone"
        assert body["results"][1]["input_url"] == "https://linkedin.com/in/persontwo"
        assert body["results"][0]["preview"]["contact_person_name"]
        assert body["results"][1]["preview"]["contact_person_name"]
        # Different slugs must produce different synthesized names.
        assert (
            body["results"][0]["preview"]["contact_person_name"]
            != body["results"][1]["preview"]["contact_person_name"]
        )

    def test_one_failing_url_does_not_affect_the_others(self, client, monkeypatch):
        monkeypatch.setattr(extractor_module, "_fetch_page", _fake_fetch_page_unreachable)

        response = client.post(
            "/api/contacts/bulk-lookup",
            json={
                "items": [
                    {"url": "https://linkedin.com/in/personone"},
                    {"url": "https://falconpetro.example"},
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["succeeded_count"] == 1
        assert body["failed_count"] == 1
        assert body["results"][0]["success"] is True
        assert body["results"][0]["preview"] is not None
        assert body["results"][1]["success"] is False
        assert body["results"][1]["error"]
        assert body["results"][1]["preview"] is None

    def test_one_item_raising_an_unexpected_error_does_not_abort_the_batch(
        self, client, monkeypatch
    ):
        # Regression test: bulk lookup used to only catch UrlLookupError,
        # so any other exception from one item (e.g. a bug, a transient
        # DB error) propagated and failed the whole batch instead of just
        # that one item.
        original_find_match = company_service.find_match

        def flaky_find_match(db, candidate, owner_id):
            if candidate.company_name == "Boom Petroleum":
                raise RuntimeError("simulated unexpected failure")
            return original_find_match(db, candidate, owner_id)

        monkeypatch.setattr(company_service, "find_match", flaky_find_match)

        response = client.post(
            "/api/contacts/bulk-lookup",
            json={
                "items": [
                    {"full_name": "Jane Doe", "company_name": "Boom Petroleum"},
                    {"full_name": "John Roe", "company_name": "Falcon Petroleum"},
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["succeeded_count"] == 1
        assert body["failed_count"] == 1
        assert body["results"][0]["success"] is False
        assert body["results"][1]["success"] is True

    def test_bulk_lookup_never_saves_anything(self, client):
        client.post(
            "/api/contacts/bulk-lookup",
            json={"items": [{"url": "https://linkedin.com/in/personone"}]},
        )
        assert client.get("/api/companies").json()["total"] == 0


class TestBulkContactLookupNameAndCompany:
    def test_mock_mode_succeeds_without_enrichment(self, client):
        response = client.post(
            "/api/contacts/bulk-lookup",
            json={"items": [{"full_name": "Jane Doe", "company_name": "Falcon Petroleum"}]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["succeeded_count"] == 1
        preview = body["results"][0]["preview"]
        assert preview["contact_person_name"] == "Jane Doe"
        assert preview["company_name"] == "Falcon Petroleum"
        assert preview["website"] is None
        assert preview["emails"] == []

    def test_enriches_with_a_found_email_when_hunter_has_a_confident_match(
        self, client, monkeypatch
    ):
        fake_provider = _FakeRealProvider(
            snippet_title="unused",
            website_url="https://falconpetro.example/about",
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        async def fake_find_person_email(*, domain, full_name, settings):
            assert domain == "falconpetro.example"
            assert full_name == "Jane Doe"
            return {"email": "jane.doe@falconpetro.example", "is_valid": True}

        monkeypatch.setattr(company_service, "find_person_email", fake_find_person_email)

        response = client.post(
            "/api/contacts/bulk-lookup",
            json={"items": [{"full_name": "Jane Doe", "company_name": "Falcon Petroleum"}]},
        )
        assert response.status_code == 200
        preview = response.json()["results"][0]["preview"]
        assert preview["website"] == "https://falconpetro.example"
        assert preview["emails"] == [{"email": "jane.doe@falconpetro.example", "is_valid": True}]

    def test_item_without_a_found_email_fails_and_others_still_succeed(self, client, monkeypatch):
        fake_provider = _FakeRealProvider(
            snippet_title="unused",
            website_url="https://falconpetro.example/about",
        )
        monkeypatch.setattr(company_service, "get_search_provider", lambda settings: fake_provider)

        async def fake_find_person_email(*, domain, full_name, settings):
            if full_name == "Jane Doe":
                return {"email": "jane.doe@falconpetro.example", "is_valid": True}
            return None

        monkeypatch.setattr(company_service, "find_person_email", fake_find_person_email)

        response = client.post(
            "/api/contacts/bulk-lookup",
            json={
                "items": [
                    {"full_name": "Jane Doe", "company_name": "Falcon Petroleum"},
                    {"full_name": "John Roe", "company_name": "Falcon Petroleum"},
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["succeeded_count"] == 1
        assert body["failed_count"] == 1
        assert body["results"][0]["success"] is True
        assert body["results"][1]["success"] is False
        assert body["results"][1]["preview"] is None
        assert "No business email found for John Roe" in body["results"][1]["error"]

    def test_mixed_url_and_name_company_items_in_one_request(self, client):
        response = client.post(
            "/api/contacts/bulk-lookup",
            json={
                "items": [
                    {"url": "https://linkedin.com/in/personone"},
                    {"full_name": "Jane Doe", "company_name": "Falcon Petroleum"},
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["succeeded_count"] == 2
        assert body["results"][0]["input_url"] == "https://linkedin.com/in/personone"
        assert body["results"][1]["input_full_name"] == "Jane Doe"
        assert body["results"][1]["input_company_name"] == "Falcon Petroleum"
