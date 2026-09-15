"""Live US-dollar prices for BTC and TRX, used to quote crypto payment amounts.

Uses CoinGecko's simple-price API — the keyless public API by default, or a
free Demo key (`COINGECKO_API_KEY`) for a steadier rate limit. Prices are
cached briefly so a burst of checkouts doesn't hit that limit. USDT isn't
quoted: it's priced 1:1 with the dollar.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation

import httpx

from app.config import Settings

logger = logging.getLogger("petrolead.services.crypto_rates")

PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_IDS = {"BTC": "bitcoin", "TRX": "tron"}
CACHE_SECONDS = 60

_cache: dict[str, tuple[float, Decimal]] = {}


class RateUnavailableError(Exception):
    """The current price couldn't be fetched."""


async def usd_price(currency: str, *, settings: Settings) -> Decimal:
    """US dollars per one coin of `currency` (BTC or TRX)."""
    cached = _cache.get(currency)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    coin_id = COINGECKO_IDS[currency]
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(
                PRICE_URL, params={"ids": coin_id, "vs_currencies": "usd"}, headers=headers
            )
            response.raise_for_status()
            price = Decimal(str(response.json()[coin_id]["usd"]))
    except (httpx.HTTPError, KeyError, TypeError, ValueError, InvalidOperation) as exc:
        logger.warning("Couldn't fetch the %s price: %s", currency, exc)
        raise RateUnavailableError(currency) from exc

    if price <= 0:
        raise RateUnavailableError(currency)
    _cache[currency] = (time.monotonic(), price)
    return price
