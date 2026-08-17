from app.discovery.relevance import score_relevance


class TestRelevanceScoring:
    def test_clear_petroleum_trading_company_scores_high(self):
        result = score_relevance(
            company_name="Gulf Petroleum Trading LLC",
            description="A leading petroleum trading company supplying EN590 diesel and jet A1 "
            "to clients across the Middle East, operating a tank storage terminal in Fujairah.",
            products=["EN590", "Diesel", "Jet A1"],
            industry="Petroleum Trading",
        )
        assert result.score >= 80
        assert result.tier == "Highly Relevant"
        assert "en590" in result.matched_terms

    def test_unrelated_company_scores_low(self):
        result = score_relevance(
            company_name="Sunny Daycare Center",
            description="We provide childcare and early education services for toddlers.",
        )
        assert result.score < 30
        assert result.tier == "Low"

    def test_empty_input_scores_zero(self):
        result = score_relevance()
        assert result.score == 0
        assert result.tier == "Low"

    def test_score_is_bounded_between_0_and_100(self):
        result = score_relevance(
            company_name="petroleum oil trading fuel trading energy trading refinery "
            "bunkering tank storage terminal crude oil diesel en590",
            description="oil and gas petroleum products fuel supplier petroleum supplier",
        )
        assert 0 <= result.score <= 100

    def test_negative_terms_reduce_score(self):
        jelly_result = score_relevance(
            company_name="SoftSkin Petroleum Jelly Co",
            description="Manufacturer of petroleum jelly and skincare products using vaseline.",
        )
        trading_result = score_relevance(
            company_name="SoftSkin Petroleum Trading Co",
            description="Petroleum trading company for fuel and diesel.",
        )
        assert jelly_result.score < trading_result.score

    def test_moderate_signal_is_possible_tier(self):
        result = score_relevance(
            company_name="Atlas Energy Company", description="A fuel business."
        )
        assert 0 <= result.score < 60
