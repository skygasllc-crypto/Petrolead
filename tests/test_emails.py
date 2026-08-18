import pytest
from bs4 import BeautifulSoup

from app.discovery.emails import extract_emails, validate_email_domain

BASE_URL = "https://example-petroleum.test"


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestExtractEmails:
    def test_extracts_mailto_link(self):
        html = '<a href="mailto:info@example-petroleum.test">Email us</a>'
        assert extract_emails(soup_of(html), "") == ["info@example-petroleum.test"]

    def test_extracts_plaintext_email(self):
        text = "For enquiries contact sales@example-petroleum.test today."
        assert extract_emails(soup_of("<p></p>"), text) == ["sales@example-petroleum.test"]

    def test_deduplicates_across_mailto_and_text(self):
        html = '<a href="mailto:info@example-petroleum.test">Email</a>'
        text = "Reach us at info@example-petroleum.test"
        assert extract_emails(soup_of(html), text) == ["info@example-petroleum.test"]

    def test_excludes_placeholder_domains(self):
        text = "contact@example.com or admin@wixpress.com"
        assert extract_emails(soup_of("<p></p>"), text) == []

    def test_excludes_asset_filename_false_positives(self):
        text = "background-image: url(logo@2x.png);"
        assert extract_emails(soup_of("<p></p>"), text) == []

    def test_ignores_mailto_query_string(self):
        html = '<a href="mailto:info@example-petroleum.test?subject=Hello">Email</a>'
        assert extract_emails(soup_of(html), "") == ["info@example-petroleum.test"]

    def test_no_emails_returns_empty_list(self):
        assert extract_emails(soup_of("<p>No contact info here.</p>"), "No contact info") == []


class TestValidateEmailDomain:
    @pytest.mark.asyncio
    async def test_nonexistent_domain_is_invalid_or_unverified(self):
        # `.invalid` is reserved by RFC 2606 to never resolve — safe to
        # assert against without depending on any specific real domain.
        result = await validate_email_domain("someone@nowhere.invalid")
        assert result in (False, None)

    @pytest.mark.asyncio
    async def test_malformed_email_is_invalid(self):
        assert await validate_email_domain("not-an-email") is False
