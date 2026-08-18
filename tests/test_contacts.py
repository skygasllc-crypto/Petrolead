from bs4 import BeautifulSoup

from app.discovery.contacts import find_contact_page, find_social_profiles

BASE_URL = "https://example-petroleum.test"


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestFindContactPage:
    def test_finds_link_by_text(self):
        html = '<a href="/reach-us">Contact Us</a>'
        assert find_contact_page(soup_of(html), BASE_URL) == f"{BASE_URL}/reach-us"

    def test_finds_link_by_href_hint(self):
        html = '<a href="/contact-us">Get in touch</a>'
        assert find_contact_page(soup_of(html), BASE_URL) == f"{BASE_URL}/contact-us"

    def test_resolves_relative_url_against_base(self):
        html = '<a href="contact">Contact</a>'
        assert find_contact_page(soup_of(html), BASE_URL) == f"{BASE_URL}/contact"

    def test_returns_none_when_no_contact_link(self):
        html = '<a href="/about">About</a><a href="/products">Products</a>'
        assert find_contact_page(soup_of(html), BASE_URL) is None

    def test_ignores_mailto_and_tel_links(self):
        html = '<a href="mailto:info@example.test">Contact</a>'
        assert find_contact_page(soup_of(html), BASE_URL) is None


class TestFindSocialProfiles:
    def test_finds_linkedin_and_facebook(self):
        html = """
        <a href="https://www.linkedin.com/company/example-petroleum">LinkedIn</a>
        <a href="https://facebook.com/examplepetroleum">Facebook</a>
        """
        profiles = find_social_profiles(soup_of(html), BASE_URL)
        platforms = {p["platform"] for p in profiles}
        assert platforms == {"linkedin", "facebook"}

    def test_x_and_twitter_domains_both_map_to_twitter(self):
        html = '<a href="https://x.com/examplepetro">X</a>'
        profiles = find_social_profiles(soup_of(html), BASE_URL)
        assert profiles == [{"platform": "twitter", "url": "https://x.com/examplepetro"}]

    def test_ignores_unrelated_links(self):
        html = '<a href="/about">About</a><a href="https://google.com">Google</a>'
        assert find_social_profiles(soup_of(html), BASE_URL) == []

    def test_first_match_per_platform_wins(self):
        html = """
        <a href="https://linkedin.com/company/first">LinkedIn 1</a>
        <a href="https://linkedin.com/company/second">LinkedIn 2</a>
        """
        profiles = find_social_profiles(soup_of(html), BASE_URL)
        assert len(profiles) == 1
        assert profiles[0]["url"] == "https://linkedin.com/company/first"

    def test_empty_page_returns_empty_list(self):
        assert find_social_profiles(soup_of("<div>No links here</div>"), BASE_URL) == []
