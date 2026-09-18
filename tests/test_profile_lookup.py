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

    def test_truncated_title_company_is_not_reported(self):
        parsed = parse_profile_snippet(
            "Michael Jones - Senior Trading Manager at Falcon Petrol..."
        )
        assert parsed.name == "Michael Jones"
        assert parsed.company_name is None

    def test_labeled_experience_in_snippet_supplies_the_company(self):
        parsed = parse_profile_snippet(
            "Pat Patterson - Underground Experience Oil and Gas Industry",
            "Underground Experience Oil and Gas Industry · Experience: Northern "
            "Pipeline Construction · Location: Wood Dale · 25 connections on LinkedIn.",
        )
        assert parsed.name == "Pat Patterson"
        assert parsed.company_name == "Northern Pipeline Construction"

    def test_unlabeled_snippet_text_is_not_guessed_as_a_company(self):
        # "bp Purdue University" mixes an employer and a school with no
        # label — too ambiguous, must stay name-only.
        parsed = parse_profile_snippet(
            "Jacqueline Anderson - 9 years experience in Oil and Gas industry",
            "Jacqueline Anderson. 9 years experience in Oil and Gas industry. bp "
            "Purdue University. Munster, Indiana, United ...",
        )
        assert parsed.company_name is None

    def test_title_company_takes_precedence_over_snippet(self):
        parsed = parse_profile_snippet(
            "Michael Jones - Senior Trading Manager at Falcon Petroleum Trading | LinkedIn",
            "Experience: Some Other Co · Location: Dubai",
        )
        assert parsed.company_name == "Falcon Petroleum Trading"

    def test_blank_title_returns_none(self):
        assert parse_profile_snippet("   ") is None
        assert parse_profile_snippet("| LinkedIn") is None

    def test_en_dash_separates_name_from_headline(self):
        # Regression: LinkedIn titles use a hyphen, an en-dash or an em-dash
        # interchangeably. Splitting on " - " alone left an en-dash title
        # unsplit, so the entire headline was reported as the person's name
        # — which is what a real lookup showed the user.
        parsed = parse_profile_snippet(
            "Konstantin Ryazantsev – Experienced Procurement Manager in Oil ..."
        )
        assert parsed.name == "Konstantin Ryazantsev"
        # Two segments with no explicit "at Company": the headline stays
        # unclaimed as both title and employer, same as any other ambiguous
        # second segment (see the two-segment test above).
        assert parsed.title is None
        assert parsed.company_name is None

    def test_em_dash_separates_name_from_headline(self):
        parsed = parse_profile_snippet(
            "Michael Jones — Senior Trading Manager at Falcon Petroleum Trading | LinkedIn"
        )
        assert parsed.name == "Michael Jones"
        assert parsed.company_name == "Falcon Petroleum Trading"

    def test_pipe_separates_name_from_headline(self):
        parsed = parse_profile_snippet(
            "Michael Jones | Senior Trading Manager at Falcon Petroleum Trading | LinkedIn"
        )
        assert parsed.name == "Michael Jones"
        assert parsed.company_name == "Falcon Petroleum Trading"

    def test_a_hyphenated_name_is_never_split(self):
        # A dash only separates segments when it has whitespace around it,
        # so a hyphenated name survives intact.
        parsed = parse_profile_snippet("Jean-Luc Bernard - Refinery Manager at Total | LinkedIn")
        assert parsed.name == "Jean-Luc Bernard"
        assert parsed.company_name == "Total"


class TestBuildProfileSnippetQuery:
    def test_builds_a_site_scoped_query_from_the_exact_url(self):
        query = build_profile_snippet_query("https://ca.linkedin.com/in/michaellwjones/")
        assert query == "site:ca.linkedin.com/in/michaellwjones"
