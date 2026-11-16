"""Shared pytest fixtures."""

from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Provide isolated settings for testing."""
    return Settings(
        ENVIRONMENT="test",
        LOG_LEVEL="DEBUG",
        CORS_ORIGINS="http://localhost:3000,http://localhost:5173",
    )


@pytest.fixture
def app(test_settings: Settings):
    """Provide application instance for tests."""
    return create_app(settings=test_settings)


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Provide synchronous TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Provide asynchronous HTTPX client fixture."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
