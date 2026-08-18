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

    def test_list_after_discovery(self, client):
        client.post("/api/discover", json={"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] > 0

    def test_get_company_detail(self, client):
        discover_response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        company_id = discover_response.json()["companies"][0]["id"]
        response = client.get(f"/api/companies/{company_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == company_id
        assert "sources" in body

    def test_mock_discovery_includes_contact_and_social_data(self, client):
        discover_response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        company_id = discover_response.json()["companies"][0]["id"]
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
        discover_response = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        )
        company_id = discover_response.json()["companies"][0]["id"]
        assert discover_response.json()["companies"][0]["lead_score"] is not None

        response = client.get(f"/api/companies/{company_id}")
        body = response.json()
        assert len(body["emails"]) > 0
        assert len(body["phones"]) > 0
        assert body["lead_score_breakdown"]["score"] >= 0

    def test_has_email_and_has_phone_filters(self, client):
        client.post("/api/discover", json={"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies?has_email=true")
        assert response.status_code == 200
        assert response.json()["total"] > 0

    def test_product_filter(self, client):
        client.post(
            "/api/discover",
            json={"country": "United Arab Emirates", "products": ["EN590"], "limit": 10},
        )
        response = client.get("/api/companies?product=EN590")
        assert response.status_code == 200
        assert response.json()["total"] > 0

    def test_min_lead_score_filter_out_of_range_rejected(self, client):
        response = client.get("/api/companies?min_lead_score=101")
        assert response.status_code == 422


class TestExportEndpoint:
    def test_export_csv(self, client):
        client.post("/api/discover", json={"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "Company Name" in response.text
        assert "attachment" in response.headers["content-disposition"]

    def test_export_xlsx(self, client):
        client.post("/api/discover", json={"country": "United Arab Emirates", "limit": 10})
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
