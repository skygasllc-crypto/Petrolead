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

    def test_export_txt_is_addresses_only(self, client):
        """The point of the text format: a file that pastes straight into a
        mail tool. A header row would arrive as a bogus recipient, so its
        absence is the assertion that matters — the CSV test above asserts
        the opposite."""
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/emails/export?format=txt")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert ".txt" in response.headers["content-disposition"]

        lines = [line for line in response.text.splitlines() if line.strip()]
        assert lines, "expected at least one address"
        assert "Email" not in lines, "a header row would be mailed as an address"
        assert all("@" in line for line in lines)
        # Addresses only — no other exported column leaks in.
        assert not any("," in line for line in lines)

    def test_export_txt_with_no_emails_still_succeeds(self, client):
        """An empty result must be an empty file, not a crash: the text
        branch indexes a column that a column-less empty frame lacks."""
        response = client.get("/api/emails/export?format=txt")
        assert response.status_code == 200
        assert response.text.strip() == ""

    def test_export_rejects_invalid_format(self, client):
        response = client.get("/api/emails/export?format=pdf")
        assert response.status_code == 422

    def test_export_with_no_emails_still_succeeds(self, client):
        response = client.get("/api/emails/export?format=csv")
        assert response.status_code == 200
