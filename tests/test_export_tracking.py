"""Marking companies/emails as exported (and filtering on it), plus the
"emails don't re-extract once set" fix — both from the same follow-up ask."""

from tests.helpers import discover_and_save


class TestCompanyExportTracking:
    def test_export_stamps_exported_at(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})

        before = client.get("/api/companies").json()["items"]
        assert len(before) > 0
        assert all(c["exported_at"] is None for c in before)

        client.get("/api/companies/export?format=csv")

        after = client.get("/api/companies").json()["items"]
        assert all(c["exported_at"] is not None for c in after)

    def test_has_exported_filter(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        client.get("/api/companies/export?format=csv")

        not_exported = client.get("/api/companies?has_exported=false").json()
        exported = client.get("/api/companies?has_exported=true").json()
        assert not_exported["total"] == 0
        assert exported["total"] > 0

    def test_csv_includes_exported_date_column(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/companies/export?format=csv")
        assert "Exported Date" in response.text


class TestEmailExportTracking:
    def test_export_stamps_exported_at(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})

        before = client.get("/api/emails").json()["items"]
        assert len(before) > 0
        assert all(e["exported_at"] is None for e in before)

        client.get("/api/emails/export?format=csv")

        after = client.get("/api/emails").json()["items"]
        assert all(e["exported_at"] is not None for e in after)

    def test_has_exported_filter(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        client.get("/api/emails/export?format=csv")

        not_exported = client.get("/api/emails?has_exported=false").json()
        exported = client.get("/api/emails?has_exported=true").json()
        assert not_exported["total"] == 0
        assert exported["total"] > 0

    def test_csv_includes_exported_date_column(self, client):
        discover_and_save(client, {"country": "United Arab Emirates", "limit": 10})
        response = client.get("/api/emails/export?format=csv")
        assert "Exported Date" in response.text


class TestEmailsAreNotReExtracted:
    """Once a company has emails, re-saving a preview that dedup-matches
    it (e.g. re-running the same search and saving again) must never
    add/replace/re-validate them — the first extraction is treated as
    final."""

    def test_resaving_an_already_saved_company_does_not_change_its_emails(self, client):
        _, save_response = discover_and_save(
            client, {"country": "United Arab Emirates", "limit": 10}
        )
        company_id = save_response.json()["results"][0]["id"]
        emails_after_first = client.get(f"/api/companies/{company_id}").json()["emails"]
        assert len(emails_after_first) > 0

        # Re-run the same search: at least one preview should now come
        # back flagged already_saved, matching that same company. Saving
        # it again exercises the merge path (not the create path).
        second_preview = client.post(
            "/api/discover", json={"country": "United Arab Emirates", "limit": 10}
        ).json()
        already_saved = next(
            c for c in second_preview["companies"] if c["existing_company_id"] == company_id
        )
        client.post("/api/companies/save", json=already_saved)

        emails_after_resave = client.get(f"/api/companies/{company_id}").json()["emails"]
        assert emails_after_resave == emails_after_first
