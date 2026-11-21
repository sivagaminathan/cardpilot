"""Tests for T35 API security hardening: Problem Details, CORS, headers, rate limiting."""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.security import SlidingWindowRateLimiter, _extract_client_key
from app.config import Settings
from app.main import create_app


def _test_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "ENVIRONMENT": "test",
        "CORS_ORIGINS": "http://localhost:5173",
        "RATE_LIMIT_ENABLED": True,
        "RATE_LIMIT_REQUESTS": 3,
        "RATE_LIMIT_WINDOW_SECONDS": 60,
        "TRUST_PROXY_HEADERS": True,
        "TRUSTED_PROXY_COUNT": 1,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_cors_normalization_and_validation() -> None:
    """CORS strips whitespace/trailing slashes, deduplicates, and rejects invalid/wildcard."""
    normalized = Settings(
        ENVIRONMENT="production",
        CORS_ORIGINS=" https://a.example.com/ , https://b.example.com , https://a.example.com ",
    )
    assert normalized.is_production is True
    assert normalized.cors_origin_list == ["https://a.example.com", "https://b.example.com"]

    for bad_env, bad_origins in [
        ("production", "*"),
        ("production", "  "),
        ("production", "ftp://example.com"),
        ("production", "not-a-url"),
        ("production", "https://example.com/with-path"),
        ("development", "ftp://localhost:5173"),
    ]:
        with pytest.raises(ValueError):
            Settings(ENVIRONMENT=bad_env, CORS_ORIGINS=bad_origins)


@pytest.mark.asyncio
async def test_cors_preflight_allowed_and_disallowed_origins() -> None:
    """CORS allows configured origin with explicit methods/headers and blocks unknown origins."""
    app = create_app(_test_settings(CORS_ORIGINS="https://app.cardpilot.demo/"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        allowed = await client.options(
            "/api/v1/categories",
            headers={
                "Origin": "https://app.cardpilot.demo",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://app.cardpilot.demo"
        assert "POST" in allowed.headers["access-control-allow-methods"]
        assert allowed.headers["access-control-allow-methods"] != "*"
        assert allowed.headers["x-content-type-options"] == "nosniff"
        assert allowed.headers["x-frame-options"] == "DENY"

        disallowed = await client.options(
            "/api/v1/categories",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in disallowed.headers


@pytest.mark.asyncio
async def test_security_headers_and_hsts_on_success_and_errors() -> None:
    """Security headers & RFC 9457 apply across 200/404/422/500; HSTS only in production."""
    prod_app = create_app(
        _test_settings(ENVIRONMENT="production", CORS_ORIGINS="https://app.cardpilot.demo")
    )

    @prod_app.get("/api/v1/_test-boom")
    async def _prod_boom() -> None:
        raise RuntimeError("super-secret-internal-detail")

    async with AsyncClient(
        transport=ASGITransport(app=prod_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        ok = await client.get("/healthz")
        assert ok.status_code == 200
        assert ok.headers["x-content-type-options"] == "nosniff"
        assert ok.headers["x-frame-options"] == "DENY"
        assert ok.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert ok.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
        assert "max-age=31536000" in ok.headers["strict-transport-security"]
        assert "cache-control" not in ok.headers

        not_found = await client.get("/api/v1/does-not-exist")
        assert not_found.status_code == 404
        assert not_found.headers["content-type"] == "application/problem+json"
        assert not_found.headers["x-content-type-options"] == "nosniff"
        assert not_found.headers["cache-control"] == "no-store"

        invalid = await client.post("/api/v1/profiles/maya/recommendations", json={})
        assert invalid.status_code == 422
        assert invalid.headers["content-type"] == "application/problem+json"
        assert invalid.headers["x-frame-options"] == "DENY"
        assert "errors" in invalid.json()

        boom = await client.get("/api/v1/_test-boom")
        assert boom.status_code == 500
        assert boom.headers["content-type"] == "application/problem+json"
        assert boom.headers["x-content-type-options"] == "nosniff"
        assert boom.headers["cache-control"] == "no-store"
        assert "max-age=31536000" in boom.headers["strict-transport-security"]
        assert "super-secret-internal-detail" not in boom.text
        assert boom.json()["type"] == "https://cardpilot.demo/errors/internal-error"

    test_app = create_app(_test_settings(ENVIRONMENT="test"))

    @test_app.get("/api/v1/_test-boom")
    async def _test_boom() -> None:
        raise RuntimeError("secret")

    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        test_500 = await client.get("/api/v1/_test-boom")
        assert test_500.status_code == 500
        assert "strict-transport-security" not in test_500.headers


def test_forwarded_ip_extraction_prevents_spoofing() -> None:
    """Proxy extraction respects trust flag, trusted_proxy_count, and malformed inputs."""
    scope_spoofed = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"198.51.100.1, 203.0.113.10")],
        "client": ("10.0.0.2", 12345),
    }
    # Default/disabled: ignores X-Forwarded-For completely
    assert _extract_client_key(scope_spoofed, trust_proxy_headers=False) == "10.0.0.2"
    # 1 trusted proxy (Render): selects proxy-appended rightmost IP, ignoring spoofed prefix
    assert (
        _extract_client_key(scope_spoofed, trust_proxy_headers=True, trusted_proxy_count=1)
        == "203.0.113.10"
    )
    # 2 trusted proxies: selects 2nd from right
    scope_two_hops = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"198.51.100.1, 203.0.113.10, 10.0.0.5")],
        "client": ("10.0.0.2", 12345),
    }
    assert (
        _extract_client_key(scope_two_hops, trust_proxy_headers=True, trusted_proxy_count=2)
        == "203.0.113.10"
    )
    # Malformed / empty X-Forwarded-For falls back to direct ASGI client
    scope_bad = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"not-an-ip, ")],
        "client": ("10.0.0.2", 12345),
    }
    assert _extract_client_key(scope_bad, trust_proxy_headers=True) == "10.0.0.2"


@pytest.mark.asyncio
async def test_rate_limit_spoof_resistance_and_untrusted_proxy_default() -> None:
    """Rotating spoofed X-Forwarded-For prefix cannot bypass rate limit."""
    app = create_app(
        _test_settings(
            RATE_LIMIT_REQUESTS=2,
            RATE_LIMIT_WINDOW_SECONDS=60,
            TRUST_PROXY_HEADERS=True,
            TRUSTED_PROXY_COUNT=1,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Same real client IP (203.0.113.10) spoofing different leftmost IPs still hits limit!
        r1 = await client.post(
            "/api/v1/profiles/maya/recommendations",
            json={},
            headers={"X-Forwarded-For": "198.51.100.1, 203.0.113.10"},
        )
        r2 = await client.post(
            "/api/v1/profiles/maya/recommendations",
            json={},
            headers={"X-Forwarded-For": "198.51.100.2, 203.0.113.10"},
        )
        r3 = await client.post(
            "/api/v1/profiles/maya/recommendations",
            json={},
            headers={"X-Forwarded-For": "198.51.100.3, 203.0.113.10"},
        )
        assert r1.status_code == 422
        assert r2.status_code == 422
        assert r3.status_code == 429
        assert r3.headers["content-type"] == "application/problem+json"
        assert int(r3.headers["retry-after"]) >= 1
        assert r3.headers["x-content-type-options"] == "nosniff"

        # GETs remain exempt
        assert (
            await client.get("/healthz", headers={"X-Forwarded-For": "203.0.113.10"})
        ).status_code == 200
        assert (
            await client.get("/metrics", headers={"X-Forwarded-For": "203.0.113.10"})
        ).status_code == 200

    # With TRUST_PROXY_HEADERS=False, different X-Forwarded-For headers share direct client bucket
    app_untrusted = create_app(_test_settings(RATE_LIMIT_REQUESTS=1, TRUST_PROXY_HEADERS=False))
    async with AsyncClient(
        transport=ASGITransport(app=app_untrusted), base_url="http://test"
    ) as client:
        assert (
            await client.post(
                "/api/v1/profiles/maya/recommendations",
                json={},
                headers={"X-Forwarded-For": "203.0.113.10"},
            )
        ).status_code == 422
        assert (
            await client.post(
                "/api/v1/profiles/maya/recommendations",
                json={},
                headers={"X-Forwarded-For": "203.0.113.99"},
            )
        ).status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_mutations_and_bucket_pruning() -> None:
    """Concurrent mutations enforce exact limit; expired client buckets are pruned."""
    app = create_app(_test_settings(RATE_LIMIT_REQUESTS=3, RATE_LIMIT_WINDOW_SECONDS=60))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/profiles/maya/recommendations",
                    json={},
                    headers={"X-Forwarded-For": "203.0.113.50"},
                )
                for _ in range(6)
            ]
        )
        statuses = [r.status_code for r in responses]
        assert statuses.count(422) == 3
        assert statuses.count(429) == 3

        # Separate client retains independent quota
        other = await client.post(
            "/api/v1/profiles/maya/recommendations",
            json={},
            headers={"X-Forwarded-For": "203.0.113.51"},
        )
        assert other.status_code == 422

    # Deterministic bucket pruning when clock advances past window_seconds
    now = 1000.0
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10, clock=lambda: now)
    assert (await limiter.check("10.0.0.1")) == (True, 1, 0)
    assert (await limiter.check("10.0.0.2")) == (True, 1, 0)
    assert set(limiter._buckets) == {"10.0.0.1", "10.0.0.2"}

    now = 1010.1
    assert (await limiter.check("10.0.0.3")) == (True, 1, 0)
    assert set(limiter._buckets) == {"10.0.0.3"}

    # Disabled flag leaves mutation responses without rate-limit headers
    app_no_limit = create_app(_test_settings(RATE_LIMIT_ENABLED=False))
    async with AsyncClient(
        transport=ASGITransport(app=app_no_limit), base_url="http://test"
    ) as client:
        for _ in range(5):
            r = await client.post("/api/v1/profiles/maya/recommendations", json={})
            assert r.status_code == 422
            assert "x-ratelimit-limit" not in r.headers
