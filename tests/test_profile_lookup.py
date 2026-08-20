from app.discovery.profile_lookup import (
    build_profile_snippet_query,
    detect_personal_profile_platform,
    parse_profile_snippet,
)


class TestDetectPersonalProfilePlatform:
    def test_linkedin_in_path_is_personal(self):
        assert detect_personal_profile_platform("https://linkedin.com/in/jane-doe") == "linkedin"

    def test_linkedin_with_country_subdomain_is_personal(self):
        assert (
            detect_personal_profile_platform("https://ca.linkedin.com/in/michaellwjones")
            == "linkedin"
        )

    def test_linkedin_company_page_is_not_personal(self):
        assert detect_personal_profile_platform("https://linkedin.com/company/example") is None

    def test_company_website_is_not_personal(self):
        assert detect_personal_profile_platform("https://example-petroleum.com") is None

    def test_facebook_profile_is_not_recognized(self):
        # No unambiguous marker for Facebook/Twitter personal profiles —
        # deliberately left to the normal website-fetch path.
        assert detect_personal_profile_platform("https://facebook.com/jane.doe") is None


class TestParseProfileSnippet:
    def test_title_at_company_form(self):
        parsed = parse_profile_snippet(
            "Michael Jones - Senior Trading Manager at Falcon Petroleum Trading | LinkedIn"
        )
        assert parsed.name == "Michael Jones"
        assert parsed.title == "Senior Trading Manager"
        assert parsed.company_name == "Falcon Petroleum Trading"

    def test_three_segment_form(self):
        parsed = parse_profile_snippet(
            "Michael Jones - Senior Trading Manager - Falcon Petroleum Trading | LinkedIn"
        )
        assert parsed.name == "Michael Jones"
        assert parsed.title == "Senior Trading Manager"
        assert parsed.company_name == "Falcon Petroleum Trading"

    def test_ambiguous_two_segment_form_is_left_as_name_only(self):
        # No explicit "at Company" and only one segment after the name —
        # could be an employer, a school, a tagline; too ambiguous to
        # guess, so this must NOT be reported as a company (regression
        # test for a real false-positive: a profile whose second segment
        # was actually education, not an employer).
        parsed = parse_profile_snippet(
            "Michael Jones - Sheridan College University of Toronto | LinkedIn"
        )
        assert parsed.name == "Michael Jones"
        assert parsed.title is None
        assert parsed.company_name is None

    def test_name_only_form_has_no_company(self):
        parsed = parse_profile_snippet("Michael Jones | LinkedIn")
        assert parsed.name == "Michael Jones"
        assert parsed.title is None
        assert parsed.company_name is None

    def test_dash_separator_variant_of_platform_suffix(self):
        parsed = parse_profile_snippet(
            "Michael Jones - Senior Trading Manager - Falcon Petroleum Trading - LinkedIn"
        )
        assert parsed.title == "Senior Trading Manager"
        assert parsed.company_name == "Falcon Petroleum Trading"

    def test_blank_title_returns_none(self):
        assert parse_profile_snippet("   ") is None
        assert parse_profile_snippet("| LinkedIn") is None


class TestBuildProfileSnippetQuery:
    def test_builds_a_site_scoped_query_from_the_exact_url(self):
        query = build_profile_snippet_query("https://ca.linkedin.com/in/michaellwjones/")
        assert query == "site:ca.linkedin.com/in/michaellwjones"
