from app.discovery.lead_scoring import compute_lead_score


class TestComputeLeadScore:
    def test_fully_complete_high_relevance_company_scores_high(self):
        result = compute_lead_score(
            relevance_score=100,
            has_website=True,
            has_contact_page=True,
            has_social_profile=True,
            has_verified_email=True,
            has_verified_phone=True,
        )
        assert result.score == 100

    def test_bare_minimum_company_scores_low(self):
        result = compute_lead_score(
            relevance_score=0,
            has_website=False,
            has_contact_page=False,
            has_social_profile=False,
            has_verified_email=False,
            has_verified_phone=False,
        )
        assert result.score == 0

    def test_relevance_alone_contributes_half_weight(self):
        result = compute_lead_score(
            relevance_score=100,
            has_website=False,
            has_contact_page=False,
            has_social_profile=False,
            has_verified_email=False,
            has_verified_phone=False,
        )
        assert result.relevance_component == 50
        assert result.score == 50

    def test_verified_email_and_phone_each_add_their_own_component(self):
        with_neither = compute_lead_score(
            relevance_score=50,
            has_website=True,
            has_contact_page=True,
            has_social_profile=True,
            has_verified_email=False,
            has_verified_phone=False,
        )
        with_both = compute_lead_score(
            relevance_score=50,
            has_website=True,
            has_contact_page=True,
            has_social_profile=True,
            has_verified_email=True,
            has_verified_phone=True,
        )
        assert with_both.score > with_neither.score
        assert with_both.verified_email_component > 0
        assert with_both.verified_phone_component > 0

    def test_score_is_bounded_between_0_and_100(self):
        result = compute_lead_score(
            relevance_score=100,
            has_website=True,
            has_contact_page=True,
            has_social_profile=True,
            has_verified_email=True,
            has_verified_phone=True,
        )
        assert 0 <= result.score <= 100
