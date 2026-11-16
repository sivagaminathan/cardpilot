"""Tests for application health and startup endpoints."""

from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_healthz_sync(client: TestClient) -> None:
    """Test that GET /healthz returns 200 and valid status payload synchronously."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "CardPilot"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "test"


async def test_healthz_async(async_client: AsyncClient) -> None:
    """Test that GET /healthz works asynchronously with httpx."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "test"


def test_openapi_schema(client: TestClient) -> None:
    """Test that OpenAPI specification generates properly."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "CardPilot"
    assert "/healthz" in schema["paths"]


def test_not_found_problem_details(client: TestClient) -> None:
    """Test that 404 responses conform to RFC 9457 Problem Details."""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    data = response.json()
    assert data["status"] == 404
    assert "title" in data
    assert "instance" in data
    assert data["instance"] == "/nonexistent-endpoint"

