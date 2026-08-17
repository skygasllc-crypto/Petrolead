from app.discovery.normalizer import extract_domain, normalize_company_name


class TestNormalizeCompanyName:
    def test_strips_llc_variants_to_the_same_key(self):
        variants = [
            "ABC Petroleum Trading LLC",
            "ABC Petroleum Trading L.L.C.",
            "ABC Petroleum Trading",
            "ABC PETROLEUM TRADING",
        ]
        normalized = {normalize_company_name(v) for v in variants[:3]}
        assert len(normalized) == 1

    def test_case_insensitive(self):
        assert normalize_company_name("ABC PETROLEUM") == normalize_company_name("abc petroleum")

    def test_removes_punctuation_and_collapses_whitespace(self):
        assert normalize_company_name("A.B.C.   Petroleum,  Inc.") == "a b c petroleum"

    def test_strips_common_corporate_suffixes(self):
        assert normalize_company_name("Gulf Energy Ltd") == "gulf energy"
        assert normalize_company_name("Gulf Energy Limited") == "gulf energy"
        assert normalize_company_name("Gulf Energy FZE") == "gulf energy"
        assert normalize_company_name("Gulf Energy DMCC") == "gulf energy"
        assert normalize_company_name("Gulf Energy GmbH") == "gulf energy"

    def test_does_not_destroy_meaningful_differences(self):
        assert normalize_company_name("Gulf Energy") != normalize_company_name("Gulf Oil")

    def test_empty_input(self):
        assert normalize_company_name("") == ""
        assert normalize_company_name(None) == ""

    def test_ampersand_normalized_to_and(self):
        assert normalize_company_name("Smith & Sons Petroleum") == normalize_company_name(
            "Smith and Sons Petroleum"
        )


class TestExtractDomain:
    def test_extracts_host_without_www(self):
        assert extract_domain("https://www.example.com/about") == "example.com"

    def test_handles_bare_domain(self):
        assert extract_domain("example.com") == "example.com"

    def test_lowercases(self):
        assert extract_domain("https://EXAMPLE.COM") == "example.com"

    def test_none_and_empty(self):
        assert extract_domain(None) is None
        assert extract_domain("") is None
