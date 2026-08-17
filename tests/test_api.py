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

    def test_pagination_bounds(self, client):
        response = client.get("/api/companies?page_size=500")
        assert response.status_code == 422
        response = client.get("/api/companies?page=0")
        assert response.status_code == 422

    def test_min_relevance_filter(self, client):
        response = client.get("/api/companies?min_relevance=101")
        assert response.status_code == 422


class TestSearchesEndpoint:
    def test_search_history_recorded(self, client):
        client.post("/api/discover", json={"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/searches")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert body["items"][0]["status"] == "completed"
