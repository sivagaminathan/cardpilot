"""Tests for /readyz readiness endpoint and database connectivity."""

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.api.deps import get_db_session
from app.main import create_app


@pytest.mark.asyncio
async def test_readyz_healthy_db(async_client: AsyncClient) -> None:
    """Test /readyz returns 200 and ready status when database is reachable."""
    response = await async_client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_readyz_database_down() -> None:
    """Test /readyz returns 503 Problem Details when database connectivity fails."""
    app = create_app()

    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise OperationalError("connection refused", params=None, orig=Exception("DB down"))

    async def broken_db_session():
        yield BrokenSession()

    app.dependency_overrides[get_db_session] = broken_db_session

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == 503
    assert "Database unreachable" in data["detail"]
