"""Tests for live price fetching.

These never touch the network: `_fetch_price` is replaced so each test
decides exactly what the upstream API does.

The behaviour under test is mostly about failure. CoinGecko rate-limits by
IP, and on shared cloud egress a good share of requests come back 429 —
which was reaching customers as a failed checkout.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.config import Settings
from app.services import crypto_rates
from app.services.crypto_rates import RateUnavailableError, usd_price

SETTINGS = Settings(http_timeout_seconds=5)


@pytest.fixture(autouse=True)
def _clear_cache():
    crypto_rates.reset_cache()
    yield
    crypto_rates.reset_cache()


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """Retries back off; tests shouldn't wait for it."""

    async def instant(_seconds):
        return None

    monkeypatch.setattr(crypto_rates.asyncio, "sleep", instant)


def _fetcher(monkeypatch, *results):
    """Queue up what each successive fetch does — a Decimal to return, or an
    exception to raise. Returns the list of calls made."""
    calls = []
    queue = list(results)

    async def fake_fetch(currency, *, settings):
        calls.append(currency)
        outcome = queue.pop(0) if queue else queue_default
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    queue_default = results[-1] if results else Decimal("1")
    monkeypatch.setattr(crypto_rates, "_fetch_price", fake_fetch)
    return calls


class TestSuccess:
    async def test_returns_the_fetched_price(self, monkeypatch):
        _fetcher(monkeypatch, Decimal("0.334"))
        assert await usd_price("TRX", settings=SETTINGS) == Decimal("0.334")

    async def test_a_fresh_price_is_not_fetched_twice(self, monkeypatch):
        calls = _fetcher(monkeypatch, Decimal("76000"))
        await usd_price("BTC", settings=SETTINGS)
        await usd_price("BTC", settings=SETTINGS)
        assert len(calls) == 1, "the cache should have answered the second call"

    async def test_each_currency_is_cached_separately(self, monkeypatch):
        calls = _fetcher(monkeypatch, Decimal("76000"), Decimal("0.334"))
        await usd_price("BTC", settings=SETTINGS)
        await usd_price("TRX", settings=SETTINGS)
        assert calls == ["BTC", "TRX"]


class TestRetrying:
    async def test_a_momentary_failure_is_retried(self, monkeypatch):
        """One 429 shouldn't reach the customer — this is the common case."""
        calls = _fetcher(
            monkeypatch,
            httpx.HTTPError("429 Too Many Requests"),
            Decimal("0.334"),
        )
        assert await usd_price("TRX", settings=SETTINGS) == Decimal("0.334")
        assert len(calls) == 2

    async def test_it_gives_up_after_the_maximum(self, monkeypatch):
        calls = _fetcher(monkeypatch, *[httpx.HTTPError("429")] * 5)
        with pytest.raises(RateUnavailableError):
            await usd_price("TRX", settings=SETTINGS)
        assert len(calls) == crypto_rates.MAX_ATTEMPTS

    async def test_a_malformed_response_is_treated_as_a_failure(self, monkeypatch):
        _fetcher(monkeypatch, *[KeyError("tron")] * 5)
        with pytest.raises(RateUnavailableError):
            await usd_price("TRX", settings=SETTINGS)


class TestStaleFallback:
    async def test_a_recent_price_is_reused_when_every_attempt_fails(self, monkeypatch):
        """The point of the change: a slightly old price beats a dead checkout."""
        _fetcher(monkeypatch, Decimal("0.334"))
        assert await usd_price("TRX", settings=SETTINGS) == Decimal("0.334")

        # Age the cached entry past the fresh window, but well inside stale.
        stamp, price = crypto_rates._cache["TRX"]
        crypto_rates._cache["TRX"] = (stamp - (crypto_rates.CACHE_SECONDS + 30), price)

        _fetcher(monkeypatch, *[httpx.HTTPError("429")] * 5)
        assert await usd_price("TRX", settings=SETTINGS) == Decimal("0.334")

    async def test_a_price_too_old_to_trust_is_refused(self, monkeypatch):
        _fetcher(monkeypatch, Decimal("0.334"))
        await usd_price("TRX", settings=SETTINGS)

        stamp, price = crypto_rates._cache["TRX"]
        crypto_rates._cache["TRX"] = (stamp - (crypto_rates.STALE_AFTER_SECONDS + 60), price)

        _fetcher(monkeypatch, *[httpx.HTTPError("429")] * 5)
        with pytest.raises(RateUnavailableError):
            await usd_price("TRX", settings=SETTINGS)

    async def test_with_no_cache_at_all_it_still_fails(self, monkeypatch):
        """First-ever request during an outage has nothing to fall back on."""
        _fetcher(monkeypatch, *[httpx.HTTPError("429")] * 5)
        with pytest.raises(RateUnavailableError):
            await usd_price("BTC", settings=SETTINGS)
