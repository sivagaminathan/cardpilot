"""Integration tests for seed loader, recommendation API, and dev fault injection."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import Settings
from app.db import close_engine, get_session_maker
from app.main import create_app
from app.models import CardProduct, Profile
from app.seeds.loader import seed_all


@pytest.mark.asyncio
async def test_seed_all_idempotent_and_recommendation_e2e(
    async_client: AsyncClient,
) -> None:
    """Seeding twice creates no duplicates and /recommendations evaluates real DB rules."""
    await close_engine()
    session_factory = get_session_maker()
    async with session_factory() as session:
        async with session.begin():
            await seed_all(session)
        async with session.begin():
            await seed_all(session)

        profile_count = await session.scalar(select(func.count()).select_from(Profile))
        product_count = await session.scalar(select(func.count()).select_from(CardProduct))
        assert profile_count is not None and profile_count >= 2
        assert product_count is not None and product_count >= 6

    profiles_res = await async_client.get("/api/v1/profiles")
    assert profiles_res.status_code == 200
    slugs = {p["slug"] for p in profiles_res.json()}
    assert {"maya", "dev"}.issubset(slugs)

    cats_res = await async_client.get("/api/v1/categories")
    assert cats_res.status_code == 200
    assert any(c["code"] == "groceries" for c in cats_res.json())

    rec_res = await async_client.post(
        "/api/v1/profiles/maya/recommendations",
        json={
            "amount_cents": 12500,
            "category_code": "groceries",
            "purchase_date": "2026-08-15",
        },
    )
    assert rec_res.status_code == 200
    data = rec_res.json()
    assert len(data["ranked"]) >= 1
    assert data["ranked"][0]["card_name"] == "Grocery 5x"
    assert data["ranked"][0]["estimated_value_cents"] == 625
    assert any(
        u["card_name"] == "Skyward Explorer" and u["reason"] == "no_valuation"
        for u in data["unranked"]
    )
    assert len(data["global_notes"]) >= 1


@pytest.mark.asyncio
async def test_dev_fault_injection_triggers_500_in_dev_and_blocked_in_prod() -> None:
    """Fault injection returns 500 in development and is impossible in production."""
    prod_settings = Settings(ENVIRONMENT="production", DEV_FAULT_INJECT_RECOMMENDATIONS=True)
    assert prod_settings.is_dev_fault_injection_active is False

    dev_settings = Settings(ENVIRONMENT="development", DEV_FAULT_INJECT_RECOMMENDATIONS=True)
    assert dev_settings.is_dev_fault_injection_active is True

    app = create_app(dev_settings)
    await close_engine()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/profiles/maya/recommendations",
            json={"amount_cents": 12500, "category_code": "groceries"},
        )
        assert res.status_code == 500
        body = res.json()
        assert body["status"] == 500
        assert "Traceback" not in str(body)
