"""Stops the app being used to reach private networks (SSRF).

`POST /api/discover-url` fetches a URL the caller chose, and the extractor
follows redirects. Without a check, any account holder could point it at
`http://169.254.169.254/` — the cloud metadata service, which on most
managed platforms hands out credentials to anything that asks — or at
`http://127.0.0.1:8000/` (this API), or at any other host inside the
deployment's network, and read the response back out of the preview. That
is server-side request forgery.

The fix is to resolve the hostname first and refuse anything that isn't a
public address. Every redirect is re-checked too, because a public URL is
free to redirect to a private one.

Known limit, stated plainly: the name is resolved here and then again by
the socket layer when the connection is made, so a DNS record that changes
between the two (DNS rebinding) can still slip through. Closing that
properly means pinning the connection to the address that was validated,
which httpx doesn't expose. The remaining window is small, and what an
attacker gets through it is a single GET whose body is only ever shown back
to the account that asked for it.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket

import httpx

logger = logging.getLogger("petrolead.core.net_guard")

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Redirect chains are capped: each hop is another request we make on the
# caller's behalf, and a long chain is a cheap way to waste our time.
MAX_REDIRECTS = 5


class BlockedURLError(Exception):
    """The URL points somewhere the app must not fetch from."""


def _is_public_ip(ip: str) -> bool:
    address = ipaddress.ip_address(ip)
    # `is_private` already covers RFC1918, unique-local IPv6 (fc00::/7) and
    # a few others; the rest are spelled out so the intent is readable.
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local  # 169.254.0.0/16 — the metadata service
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


async def _resolve_ips(host: str, port: int) -> list[str]:
    """Every address `host` resolves to. Overridden in tests so they never
    depend on DNS."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


async def assert_public_url(url: httpx.URL | str) -> None:
    """Raise `BlockedURLError` unless `url` is http(s) on a public address."""
    url = httpx.URL(str(url))

    if url.scheme not in ALLOWED_SCHEMES:
        raise BlockedURLError(f"Only http and https links can be fetched, not {url.scheme!r}.")

    host = url.host
    if not host:
        raise BlockedURLError("That link has no hostname.")

    port = url.port or (443 if url.scheme == "https" else 80)
    try:
        ips = await _resolve_ips(host, port)
    except (OSError, socket.gaierror) as exc:
        raise BlockedURLError(f"Could not look up {host}.") from exc

    if not ips:
        raise BlockedURLError(f"Could not look up {host}.")

    # Every address must be public: a host that resolves to both a public
    # and a private address is a standard way to sneak past a check like
    # this one.
    for ip in ips:
        if not _is_public_ip(ip):
            logger.warning("Blocked an attempt to fetch a non-public address: %s -> %s", host, ip)
            raise BlockedURLError(
                "That link points to a private or internal address, which this service "
                "won't fetch. Use a public website address."
            )


async def block_internal_requests(request: httpx.Request) -> None:
    """httpx request hook: runs for the first request and for every redirect."""
    await assert_public_url(request.url)
