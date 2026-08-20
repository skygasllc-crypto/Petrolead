from tests.helpers import discover_and_save


class TestEmailsEndpoint:
    def test_empty_initially(self, client):
        response = client.get("/api/emails")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_lists_emails_after_discovery_and_save(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/emails")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] > 0
        first = body["items"][0]
        assert "@" in first["email"]
        assert first["company_name"]
        assert first["company_id"]

    def test_search_filter(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        all_emails = client.get("/api/emails").json()["items"]
        sample = all_emails[0]["email"].split("@")[0]

        response = client.get(f"/api/emails?search={sample}")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

        response = client.get("/api/emails?search=zzz-no-such-email-zzz")
        assert response.json()["total"] == 0

    def test_is_valid_filter(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/emails?is_valid=true")
        assert response.status_code == 200
        # Mock emails are synthesized with is_valid=None (pending), so an
        # is_valid=true filter should legitimately return zero here.
        assert response.json()["total"] == 0

    def test_pagination_bounds(self, client):
        response = client.get("/api/emails?page_size=500")
        assert response.status_code == 422


class TestEmailsExportEndpoint:
    def test_export_csv(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/emails/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "Email" in response.text
        assert "attachment" in response.headers["content-disposition"]

    def test_export_xlsx(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/emails/export?format=xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]

    def test_export_rejects_invalid_format(self, client):
        response = client.get("/api/emails/export?format=pdf")
        assert response.status_code == 422

    def test_export_with_no_emails_still_succeeds(self, client):
        response = client.get("/api/emails/export?format=csv")
        assert response.status_code == 200
