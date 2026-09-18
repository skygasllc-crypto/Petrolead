"""Settings that are wrong in a way that looks right.

A misconfigured value is more dangerous than a missing one: missing is
visible, wrong is silent. These cover the cases where a bad value would be
handed to a provider — or to a customer — instead of being refused.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.discovery import email_verification as verification


class TestPlaceholderValues:
    """Every placeholder in .env.example and the docs is written `<like
    this>`. Pasting one whole is an easy mistake, and it used to fail
    silently: a verification key of `<your-key>` was refused by the
    provider, every address fell back to the DNS-only check, and the
    customer was told their good addresses were risky.
    """

    @pytest.mark.parametrize(
        "raw",
        [
            "<your-api-key>",
            "<YOUR_KEY_HERE>",
            "  <your-api-key>  ",
            "<>",
        ],
    )
    def test_a_bracketed_key_is_treated_as_unset(self, raw):
        assert Settings(email_verify_api_key=raw).email_verify_api_key is None

    def test_a_placeholder_key_disables_the_provider_rather_than_failing_every_address(self):
        """The whole point: unset is visible. The verifier page says no
        provider is configured, instead of grading good addresses risky."""
        settings = Settings(
            email_verify_provider="millionverifier", email_verify_api_key="<your-api-key>"
        )
        assert verification.get_provider(settings) is None

    def test_a_placeholder_wallet_address_never_reaches_checkout(self):
        """The most expensive case. A placeholder shown at checkout is an
        address a customer can send real money to, unrecoverably."""
        settings = Settings(
            crypto_btc_address="<your btc address>",
            crypto_trx_address="<TRX_ADDRESS>",
            crypto_usdt_trc20_address="<usdt address>",
        )
        assert settings.crypto_btc_address is None
        assert settings.crypto_trx_address is None
        assert settings.crypto_usdt_trc20_address is None

    def test_placeholders_are_caught_across_every_provider_key(self):
        settings = Settings(
            serper_api_key="<key>",
            hunter_io_api_key="<key>",
            prospeo_api_key="<key>",
            coingecko_api_key="<key>",
        )
        assert settings.serper_api_key is None
        assert settings.hunter_io_api_key is None
        assert settings.prospeo_api_key is None
        assert settings.coingecko_api_key is None


class TestRealValuesSurvive:
    """The rule must not damage a legitimate value. It applies only when
    the whole value is bracketed, so a key that merely contains a bracket
    is kept exactly as given."""

    @pytest.mark.parametrize(
        "raw",
        [
            "abc<def",
            "<abc",
            "abc>",
            "key-with-<-inside",
        ],
    )
    def test_a_key_containing_a_bracket_is_kept(self, raw):
        assert Settings(email_verify_api_key=raw).email_verify_api_key == raw

    def test_an_ordinary_key_is_untouched(self):
        assert Settings(email_verify_api_key="mv_live_9f3a").email_verify_api_key == "mv_live_9f3a"

    def test_an_empty_value_is_still_unset(self):
        assert Settings(email_verify_api_key="").email_verify_api_key is None
        assert Settings(email_verify_api_key="   ").email_verify_api_key is None
