from bs4 import BeautifulSoup

from app.discovery.phones import extract_phone_candidates, validate_phone

BASE_URL = "https://example-petroleum.test"


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestExtractPhoneCandidates:
    def test_extracts_tel_link(self):
        html = '<a href="tel:+97142345678">Call us</a>'
        assert extract_phone_candidates(soup_of(html), "") == ["+97142345678"]

    def test_extracts_plaintext_phone(self):
        text = "Call our office at +971 4 234 5678 for more information."
        candidates = extract_phone_candidates(soup_of("<p></p>"), text)
        assert any("234" in c for c in candidates)

    def test_ignores_short_numbers(self):
        text = "Founded in 1998, unit 12."
        assert extract_phone_candidates(soup_of("<p></p>"), text) == []

    def test_deduplicates_by_digits(self):
        html = '<a href="tel:+971 4 234 5678">Call</a>'
        text = "or +971-4-234-5678"
        candidates = extract_phone_candidates(soup_of(html), text)
        assert len(candidates) == 1


class TestValidatePhone:
    def test_valid_uae_number(self):
        normalized, is_valid = validate_phone("+971 4 234 5678", country="United Arab Emirates")
        assert is_valid is True
        assert normalized.startswith("+971")

    def test_valid_number_without_country_hint_uses_leading_plus(self):
        normalized, is_valid = validate_phone("+1 415 555 2671", country=None)
        assert is_valid is True
        assert normalized.startswith("+1")

    def test_garbage_input_is_invalid(self):
        normalized, is_valid = validate_phone("not a phone number", country="United Arab Emirates")
        assert is_valid is False
        assert normalized == "not a phone number"

    def test_too_short_number_is_invalid(self):
        _, is_valid = validate_phone("12345", country="United Arab Emirates")
        assert is_valid is False
