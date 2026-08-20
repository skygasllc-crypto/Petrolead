from bs4 import BeautifulSoup

from app.discovery.extractor import _validate_and_merge_phones
from app.discovery.phones import (
    extract_phone_candidates,
    extract_phone_text_candidates,
    extract_tel_link_candidates,
    validate_phone,
)

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


class TestTelVsTextSplit:
    def test_tel_and_text_candidates_are_separated(self):
        html = '<a href="tel:+97142345678">Call</a>'
        text = "Founded 1998, build 2.3.1000, sequence 1 1 2 3 5 8 13 21 34 55"
        assert extract_tel_link_candidates(soup_of(html)) == ["+97142345678"]
        # The loose plaintext regex WILL match some of this noise — that's
        # expected and fine, since these never get surfaced unvalidated
        # (see TestValidateAndMergePhones below).
        assert extract_phone_text_candidates(text) != []


class TestValidateAndMergePhones:
    """Regression coverage for the real-world bug found testing against a
    live site: plaintext numeric noise (dates, version strings, number
    sequences) matched the loose candidate regex and was being surfaced
    as unverified "phone numbers". Fix: tel: links are trusted regardless
    of validation; plaintext matches are dropped unless they validate."""

    def test_tel_link_kept_even_when_barely_valid(self):
        entries = _validate_and_merge_phones(
            ["+971 4 234 5678"], [], country="United Arab Emirates"
        )
        assert len(entries) == 1
        assert entries[0]["is_valid"] is True

    def test_invalid_plaintext_noise_is_dropped_not_surfaced(self):
        # None of these plausibly-matching strings are real phone numbers.
        noise = ["1998", "2.3.1000", "1 1 2 3 5 8 13 21 34 55", "2026-08-13"]
        entries = _validate_and_merge_phones([], noise, country="United Arab Emirates")
        assert entries == []

    def test_valid_plaintext_number_is_kept(self):
        entries = _validate_and_merge_phones(
            [], ["+971 4 234 5678"], country="United Arab Emirates"
        )
        assert len(entries) == 1
        assert entries[0]["is_valid"] is True

    def test_deduplicates_across_tel_and_text(self):
        entries = _validate_and_merge_phones(
            ["+971 4 234 5678"], ["+971-4-234-5678"], country="United Arab Emirates"
        )
        assert len(entries) == 1

    def test_respects_max_phones_cap(self):
        tel = [f"+971 4 234 {5000 + i}" for i in range(10)]
        entries = _validate_and_merge_phones(tel, [], country="United Arab Emirates")
        assert len(entries) <= 5
