"""Live US-dollar prices for BTC and TRX, used to quote crypto payment amounts.

Uses CoinGecko's simple-price API — the keyless public API by default, or a
free Demo key (`COINGECKO_API_KEY`) for a steadier rate limit. USDT isn't
quoted: it's priced 1:1 with the dollar.

The hard part isn't fetching a price, it's that this runs on shared cloud
egress. CoinGecko rate-limits by IP, so a chunk of requests come back 429
through no fault of ours, and the customer standing at the checkout sees a
failure they can do nothing about. Three things stop that:

* a short window where a cached price is returned without asking again,
* a couple of quick retries, since throttling is usually momentary, and
* falling back to the last good price when the network won't cooperate.

That last one means a quote can be built from a price a few minutes old.
That is a deliberate trade: the alternative is refusing the sale outright,
and an order's quote is already held for `CRYPTO_QUOTE_MINUTES` after it is
created, so the design tolerates far more drift than this. Prices are only
served stale up to `STALE_AFTER_SECONDS`; beyond that the error stands.
"""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal, InvalidOperation

import httpx

from app.config import Settings

logger = logging.getLogger("petrolead.services.crypto_rates")

PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_IDS = {"BTC": "bitcoin", "TRX": "tron"}

# Serve without asking again inside this window.
CACHE_SECONDS = 60
# Beyond CACHE_SECONDS, a cached price is still used if the fetch fails —
# but only up to here. Half an hour of drift on a quote that is itself held
# for an hour is acceptable; half a day is not.
STALE_AFTER_SECONDS = 30 * 60
# Throttling is usually momentary, so a couple of quick retries clears it.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5

_cache: dict[str, tuple[float, Decimal]] = {}


class RateUnavailableError(Exception):
    """The current price couldn't be fetched."""


def reset_cache() -> None:
    """Forget every cached price. For tests — never call this from a request."""
    _cache.clear()


async def _fetch_price(currency: str, *, settings: Settings) -> Decimal:
    """One HTTP round trip. Raises on anything that isn't a usable price."""
    coin_id = COINGECKO_IDS[currency]
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        response = await client.get(
            PRICE_URL, params={"ids": coin_id, "vs_currencies": "usd"}, headers=headers
        )
        response.raise_for_status()
        price = Decimal(str(response.json()[coin_id]["usd"]))

    if price <= 0:
        raise ValueError(f"non-positive price for {currency}")
    return price


async def usd_price(currency: str, *, settings: Settings) -> Decimal:
    """US dollars per one coin of `currency` (BTC or TRX).

    Returns a cached price when it's fresh, otherwise fetches — retrying a
    few times — and falls back to the last good price rather than failing
    the customer's checkout over a momentary rate limit.
    """
    cached = _cache.get(currency)
    now = time.monotonic()
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            price = await _fetch_price(currency, settings=settings)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, InvalidOperation) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue
        _cache[currency] = (time.monotonic(), price)
        return price

    # Every attempt failed. A price from a few minutes ago beats refusing
    # the sale, so long as it isn't old enough to misquote the amount.
    if cached is not None:
        age = time.monotonic() - cached[0]
        if age < STALE_AFTER_SECONDS:
            logger.warning(
                "Using a %.0fs-old %s price after %d failed attempts: %s",
                age,
                currency,
                MAX_ATTEMPTS,
                last_error,
            )
            return cached[1]

    logger.warning(
        "Couldn't fetch the %s price after %d attempts: %s", currency, MAX_ATTEMPTS, last_error
    )
    raise RateUnavailableError(currency) from last_error
