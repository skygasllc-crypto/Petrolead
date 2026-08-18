class TestSavedSearchCrud:
    def test_create_saved_search(self, client):
        response = client.post(
            "/api/saved-searches",
            json={
                "name": "UAE diesel traders",
                "country": "United Arab Emirates",
                "products": ["EN590"],
                "limit": 10,
                "frequency": "daily",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "UAE diesel traders"
        assert body["is_active"] is True
        assert body["frequency"] == "daily"

    def test_rejects_invalid_frequency(self, client):
        response = client.post(
            "/api/saved-searches",
            json={"name": "Bad", "country": "UAE", "limit": 10, "frequency": "hourly"},
        )
        assert response.status_code == 422

    def test_rejects_blank_name(self, client):
        response = client.post(
            "/api/saved-searches", json={"name": "", "country": "UAE", "limit": 10}
        )
        assert response.status_code == 422

    def test_list_saved_searches(self, client):
        client.post(
            "/api/saved-searches", json={"name": "A", "country": "UAE", "limit": 10}
        )
        client.post(
            "/api/saved-searches", json={"name": "B", "country": "Nigeria", "limit": 25}
        )
        response = client.get("/api/saved-searches")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_toggle_active(self, client):
        created = client.post(
            "/api/saved-searches", json={"name": "A", "country": "UAE", "limit": 10}
        ).json()
        response = client.patch(
            f"/api/saved-searches/{created['id']}", params={"is_active": False}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_toggle_nonexistent_returns_404(self, client):
        response = client.patch(
            "/api/saved-searches/does-not-exist", params={"is_active": False}
        )
        assert response.status_code == 404

    def test_delete_saved_search(self, client):
        created = client.post(
            "/api/saved-searches", json={"name": "A", "country": "UAE", "limit": 10}
        ).json()
        response = client.delete(f"/api/saved-searches/{created['id']}")
        assert response.status_code == 204
        assert client.get("/api/saved-searches").json() == []

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete("/api/saved-searches/does-not-exist")
        assert response.status_code == 404


class TestRunDueSavedSearches:
    def test_new_saved_search_is_due_immediately_and_runs(self, client):
        created = client.post(
            "/api/saved-searches",
            json={"name": "UAE diesel", "country": "United Arab Emirates", "limit": 10},
        ).json()

        response = client.post("/api/saved-searches/run-due")
        assert response.status_code == 200
        assert response.json()["ran"] >= 1

        # The run should show up in search history, linked back to the saved search.
        searches = client.get("/api/searches").json()["items"]
        linked = [s for s in searches if s.get("saved_search_id") == created["id"]]
        assert len(linked) == 1
        assert linked[0]["status"] == "completed"

        # And it should have produced companies.
        companies = client.get("/api/companies").json()
        assert companies["total"] > 0

    def test_run_due_is_idempotent_within_the_same_period(self, client):
        client.post(
            "/api/saved-searches",
            json={"name": "UAE diesel", "country": "United Arab Emirates", "limit": 10},
        )
        first = client.post("/api/saved-searches/run-due").json()
        second = client.post("/api/saved-searches/run-due").json()
        assert first["ran"] >= 1
        # next_run_at was pushed into the future, so an immediate re-check finds nothing due.
        assert second["ran"] == 0

    def test_no_saved_searches_returns_zero(self, client):
        response = client.post("/api/saved-searches/run-due")
        assert response.json()["ran"] == 0
