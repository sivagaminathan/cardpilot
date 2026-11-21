"""Security response headers and mutation rate-limiting ASGI middleware (T35, NFR-6)."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import time
from collections import deque
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import ProblemDetails

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _append_header(headers: list[tuple[bytes, bytes]], name: bytes, value: bytes) -> None:
    lower_name = name.lower()
    if not any(existing_name.lower() == lower_name for existing_name, _ in headers):
        headers.append((name, value))


def get_security_headers(path: str, *, is_production: bool = False) -> list[tuple[bytes, bytes]]:
    """Return standard security headers for an HTTP response."""
    headers: list[tuple[bytes, bytes]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    ]
    if path.startswith("/api/"):
        headers.append((b"cache-control", b"no-store"))
    if is_production:
        headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    return headers


class SecurityHeadersMiddleware:
    """Attach standard security headers to all HTTP responses, including errors."""

    def __init__(self, app: ASGIApp, *, is_production: bool = False) -> None:
        self.app = app
        self.is_production = is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                for name, value in get_security_headers(path, is_production=self.is_production):
                    _append_header(headers, name, value)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


class SlidingWindowRateLimiter:
    """Thread/async-safe in-memory sliding-window rate limiter keyed by client."""

    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._buckets: dict[str, deque[float]] = {}
        self._last_prune: float = clock()
        self._lock = asyncio.Lock()

    async def check(self, client_key: str) -> tuple[bool, int, int]:
        """Record or reject a request for `client_key`.

        Returns ``(allowed, remaining, retry_after_seconds)``.
        """
        async with self._lock:
            now = self._clock()
            cutoff = now - self.window_seconds

            if now - self._last_prune >= self.window_seconds:
                expired_keys = [
                    key
                    for key, dq in self._buckets.items()
                    if key != client_key and (not dq or dq[-1] <= cutoff)
                ]
                for key in expired_keys:
                    del self._buckets[key]
                self._last_prune = now

            bucket = self._buckets.setdefault(client_key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                retry_after = max(1, math.ceil(self.window_seconds - (now - bucket[0])))
                return False, 0, retry_after

            bucket.append(now)
            remaining = max(0, self.max_requests - len(bucket))
            return True, remaining, 0


def _extract_client_key(
    scope: Scope,
    *,
    trust_proxy_headers: bool,
    trusted_proxy_count: int = 1,
) -> str:
    if trust_proxy_headers:
        for name, value in scope.get("headers", []):
            if bytes(name).lower() == b"x-forwarded-for":
                raw_parts = [
                    p.strip() for p in bytes(value).decode("latin-1").split(",") if p.strip()
                ]
                valid_ips: list[str] = []
                for part in raw_parts:
                    try:
                        valid_ips.append(str(ipaddress.ip_address(part)))
                    except ValueError:
                        continue
                if len(valid_ips) >= trusted_proxy_count:
                    return valid_ips[-trusted_proxy_count]
    client = scope.get("client")
    if client and isinstance(client, tuple | list) and len(client) >= 1 and client[0]:
        return str(client[0])
    return "unknown"


class MutationRateLimitMiddleware:
    """Rate-limit mutating API requests (POST/PUT/PATCH/DELETE) with RFC 9457 429s."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_requests: int = 60,
        window_seconds: int = 60,
        trust_proxy_headers: bool = False,
        trusted_proxy_count: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.trust_proxy_headers = trust_proxy_headers
        self.trusted_proxy_count = trusted_proxy_count
        self.limiter = SlidingWindowRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
            clock=clock,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "GET").upper()
        path: str = scope.get("path", "")
        if method not in _MUTATING_METHODS or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        client_key = _extract_client_key(
            scope,
            trust_proxy_headers=self.trust_proxy_headers,
            trusted_proxy_count=self.trusted_proxy_count,
        )
        allowed, remaining, retry_after = await self.limiter.check(client_key)

        if not allowed:
            problem = ProblemDetails(
                type="https://cardpilot.demo/errors/rate-limit-exceeded",
                title="Too Many Requests",
                status=429,
                detail="Rate limit exceeded for mutating requests. Please retry later.",
                instance=path,
            )
            body = json.dumps(problem.model_dump(exclude_none=True)).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/problem+json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                        (b"retry-after", str(retry_after).encode("ascii")),
                        (b"x-ratelimit-limit", str(self.limiter.max_requests).encode("ascii")),
                        (b"x-ratelimit-remaining", b"0"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_with_rate_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                _append_header(
                    headers,
                    b"x-ratelimit-limit",
                    str(self.limiter.max_requests).encode("ascii"),
                )
                _append_header(
                    headers,
                    b"x-ratelimit-remaining",
                    str(remaining).encode("ascii"),
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_rate_headers)
