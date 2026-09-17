"""Rate limiting and security response headers.

Rate limiting exists mainly for the login endpoint: without it, an attacker
can try passwords against a known email address as fast as the network
allows, and bcrypt alone only slows that to a few hundred guesses a second
per core. The expensive endpoints (`/discover`, `/discover-url`, bulk
lookup) are limited too, since each one costs real money in provider calls.

Counting is per process and in memory. That is a deliberate trade: it needs
no Redis round trip on every request and cannot fail open if Redis is down,
but with N web workers the effective limit is N times the configured one,
and restarting the process forgets every window. For slowing down password
guessing that is sufficient; it is not a billing control, and the credit
system — not this — is what stops an account spending money it doesn't have.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import Settings, get_settings

logger = logging.getLogger("petrolead.core.middleware")

WINDOW_SECONDS = 60

# Paths where a wrong guess is worth something to an attacker, so they get
# the stricter allowance.
AUTH_PATHS = ("/auth/login", "/auth/register")

# Stops the bookkeeping growing without bound if a lot of distinct addresses
# show up; the oldest windows are dropped first.
MAX_TRACKED_CLIENTS = 10_000


@dataclass
class _Window:
    started_at: float
    count: int


_windows: dict[tuple[str, str], _Window] = {}


def reset_rate_limits() -> None:
    """Forget every window. For tests — never call this from a request."""
    _windows.clear()


def client_key(request: Request, settings: Settings) -> str:
    """Who to count against. Behind a load balancer the socket address is
    the balancer, so the forwarded header is used instead — but only when
    the deployment says it is behind a proxy, because otherwise a caller
    could set that header themselves and get a fresh allowance per request."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit_for(path: str, settings: Settings) -> tuple[str, int]:
    for auth_path in AUTH_PATHS:
        if path.endswith(auth_path):
            return "auth", settings.auth_rate_limit_per_minute
    return "api", settings.rate_limit_per_minute


def _check(key: tuple[str, str], limit: int) -> int:
    """Count this request. Returns seconds to wait, or 0 when allowed."""
    now = time.monotonic()
    window = _windows.get(key)

    if window is None or now - window.started_at >= WINDOW_SECONDS:
        if len(_windows) >= MAX_TRACKED_CLIENTS:
            oldest = min(_windows, key=lambda k: _windows[k].started_at)
            del _windows[oldest]
        _windows[key] = _Window(started_at=now, count=1)
        return 0

    window.count += 1
    if window.count > limit:
        return max(1, int(WINDOW_SECONDS - (now - window.started_at)))
    return 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        scope, limit = _limit_for(request.url.path, settings)
        retry_after = _check((client_key(request, settings), scope), limit)
        if retry_after:
            logger.warning(
                "Rate limit hit: %s %s (%s allowance)", request.method, request.url.path, scope
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a moment and try again."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers that cost nothing and close off whole classes of attack."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        headers = response.headers

        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        settings = get_settings()
        if settings.app_env != "development":
            # Only meaningful over HTTPS, which production is.
            headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )

        # Every response here is JSON, so nothing needs to load. The
        # interactive docs are the exception: they pull scripts from a CDN.
        if not request.url.path.rstrip("/").endswith(("/docs", "/redoc", "/openapi.json")):
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )

        return response
