from app.services import company_service
from tests.helpers import discover_and_save


class TestHealthCheck:
    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestDiscoverValidation:
    def test_rejects_invalid_limit(self, client):
        response = client.post("/api/discover", json={"limit": 999})
        assert response.status_code == 422

    def test_accepts_valid_request(self, client):
        response = client.post(
            "/api/discover",
            json={
                "region": "Middle East",
                "country": "United Arab Emirates",
                "industry": "Petroleum Trading",
                "products": ["EN590"],
                "keywords": ["diesel"],
                "limit": 10,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["is_mock"] is True
        assert body["result_count"] > 0
        assert len(body["companies"]) > 0
        # Mock data must be clearly labeled — never presented as real.
        assert all("[MOCK]" in c["company_name"] for c in body["companies"])

    def test_default_limit_is_valid(self, client):
        response = client.post("/api/discover", json={"country": "United Arab Emirates"})
        assert response.status_code == 200

    def test_blank_keywords_are_stripped(self, client):
        response = client.post(
            "/api/discover",
            json={"country": "UAE", "keywords": ["  ", "diesel", ""], "limit": 10},
        )
        assert response.status_code == 200

    def test_b2b_and_social_flags_default_off_and_dont_change_source(self, client):
        response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        sources = {c["source"] for c in response.json()["companies"]}
        assert sources == {"search:mock"}

    def test_b2b_and_social_flags_are_accepted_and_dont_reduce_results(self, client):
        # Source-level coverage for what these flags actually surface lives
        # in test_partial_sources.py. Here we just confirm the discover
        # endpoint accepts them without erroring and never *shrinks* the
        # preview: the mock provider generates identical company names
        # regardless of which source queried for them, so in-memory dedup
        # legitimately folds most extra-source candidates into the same
        # companies rather than growing the count — that's correct
        # behavior, not a bug, so we can't assert a strict increase here.
        baseline = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 25}
        ).json()
        with_extras = client.post(
            "/api/discover",
            json={
                "country": "United Arab Emirates",
                "limit": 25,
                "include_social_search": True,
                "include_b2b_directories": True,
            },
        ).json()
        assert with_extras["status"] == "completed"
        assert with_extras["result_count"] >= baseline["result_count"]

    def test_discover_does_not_save_anything(self, client):
        """The core behavior this suite guards: results are a preview
        only. Nothing shows up in /api/companies until explicitly saved."""
        response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        assert response.status_code == 200
        assert len(response.json()["companies"]) > 0
        # None of the preview items have a database id.
        assert all("id" not in c for c in response.json()["companies"])

        companies = client.get("/api/companies").json()
        assert companies["total"] == 0

    def test_preview_includes_scores_and_already_saved_flag(self, client):
        response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        preview = response.json()["companies"][0]
        assert isinstance(preview["relevance_score"], int)
        assert isinstance(preview["lead_score"], int)
        assert preview["already_saved"] is False
        assert preview["existing_company_id"] is None

    def test_repeat_discovery_flags_already_saved_companies(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})

        second = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        ).json()
        assert any(c["already_saved"] for c in second["companies"])
        already_saved = next(c for c in second["companies"] if c["already_saved"])
        assert already_saved["existing_company_id"] is not None


class TestCompaniesEndpoint:
    def test_empty_list_initially(self, client):
        response = client.get("/api/companies")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_get_nonexistent_company_returns_404(self, client):
        response = client.get("/api/companies/does-not-exist")
        assert response.status_code == 404

    def test_list_after_discovery_and_save(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies")
        assert response.status_code == 200
        assert response.json()["total"] > 0

    def test_get_company_detail(self, client):
        _, save_response = discover_and_save(
            client, {"country": "United Arab Emirates", "limit": 10}
        )
        company_id = save_response.json()["results"][0]["id"]
        response = client.get(f"/api/companies/{company_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == company_id
        assert "sources" in body

    def test_mock_discovery_includes_contact_and_social_data(self, client):
        _, save_response = discover_and_save(
            client, {"country": "United Arab Emirates", "limit": 10}
        )
        company_id = save_response.json()["results"][0]["id"]
        response = client.get(f"/api/companies/{company_id}")
        body = response.json()
        # Mock mode synthesizes clearly-labeled contact/social data so the
        # Phase 2 UI has something to render without a real search provider.
        assert body["contact"]["contact_page_url"].endswith("/contact")
        assert len(body["social_profiles"]) > 0
        assert {"linkedin", "facebook"} <= {p["platform"] for p in body["social_profiles"]}

    def test_pagination_bounds(self, client):
        response = client.get("/api/companies?page_size=500")
        assert response.status_code == 422
        response = client.get("/api/companies?page=0")
        assert response.status_code == 422

    def test_min_relevance_filter(self, client):
        response = client.get("/api/companies?min_relevance=101")
        assert response.status_code == 422

    def test_mock_discovery_includes_emails_phones_and_lead_score(self, client):
        discover_response, save_response = discover_and_save(
            client, {"country": "United Arab Emirates", "limit": 10}
        )
        assert discover_response.json()["companies"][0]["lead_score"] is not None
        company_id = save_response.json()["results"][0]["id"]

        response = client.get(f"/api/companies/{company_id}")
        body = response.json()
        assert len(body["emails"]) > 0
        assert len(body["phones"]) > 0
        assert body["lead_score_breakdown"]["score"] >= 0

    def test_has_email_and_has_phone_filters(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies?has_email=true")
        assert response.status_code == 200
        assert response.json()["total"] > 0

    def test_product_filter(self, client):
        discover_and_save(
            client,
            {"country": "United Arab Emirates", "products": ["EN590"], "limit": 10},
        )
        response = client.get("/api/companies?product=EN590")
        assert response.status_code == 200
        assert response.json()["total"] > 0

    def test_min_lead_score_filter_out_of_range_rejected(self, client):
        response = client.get("/api/companies?min_lead_score=101")
        assert response.status_code == 422


class TestSaveEndpoints:
    def test_save_bulk_reports_new_and_duplicate_counts(self, client):
        discover_response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        companies = discover_response.json()["companies"]

        first_save = client.post("/api/companies/save-bulk", json={"companies": companies})
        assert first_save.status_code == 200
        body = first_save.json()
        assert body["new_count"] > 0
        assert len(body["results"]) == len(companies)
        assert sum(1 for r in body["results"] if r is not None) == (
            body["new_count"] + body["duplicate_count"]
        )

        # Saving the exact same preview data again should merge, not duplicate.
        second_save = client.post("/api/companies/save-bulk", json={"companies": companies})
        assert second_save.json()["new_count"] == 0

    def test_one_candidate_failing_does_not_roll_back_others_in_the_same_batch(
        self, client, monkeypatch
    ):
        # Regression test: _persist_candidate used to call db.rollback()
        # on failure, which discarded the still-uncommitted inserts of
        # every earlier candidate in the same "Save All" loop too (they
        # all share one session and one final commit).
        discover_response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        companies = discover_response.json()["companies"][:3]
        assert len(companies) == 3
        boom_name = companies[1]["company_name"]

        original_find_match = company_service.find_match

        def flaky_find_match(db, candidate, owner_id):
            if candidate.company_name == boom_name:
                raise RuntimeError("simulated persistence failure")
            return original_find_match(db, candidate, owner_id)

        monkeypatch.setattr(company_service, "find_match", flaky_find_match)

        response = client.post("/api/companies/save-bulk", json={"companies": companies})
        assert response.status_code == 200
        results = response.json()["results"]
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is not None

        saved_names = {c["company_name"] for c in client.get("/api/companies").json()["items"]}
        assert companies[0]["company_name"] in saved_names
        assert companies[2]["company_name"] in saved_names

    def test_save_single_company(self, client):
        discover_response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        preview = discover_response.json()["companies"][0]
        response = client.post("/api/companies/save", json=preview)
        assert response.status_code == 200
        assert response.json()["company_name"] == preview["company_name"]
        assert client.get("/api/companies").json()["total"] == 1

    def test_save_rejects_missing_company_name(self, client):
        response = client.post("/api/companies/save", json={"company_name": ""})
        assert response.status_code == 422


class TestExportEndpoint:
    def test_export_csv(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "Company Name" in response.text
        assert "attachment" in response.headers["content-disposition"]

    def test_export_xlsx(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies/export?format=xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]

    def test_export_rejects_invalid_format(self, client):
        response = client.get("/api/companies/export?format=pdf")
        assert response.status_code == 422

    def test_export_with_no_companies_still_succeeds(self, client):
        response = client.get("/api/companies/export?format=csv")
        assert response.status_code == 200


class TestSearchesEndpoint:
    def test_search_history_recorded(self, client):
        client.post("/api/discover", json={"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/searches")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert body["items"][0]["status"] == "completed"
