"""PostgreSQL integration tests for profile currency valuations (T27)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient

from app.db import close_engine, get_session_maker
from app.seeds.loader import seed_all


@pytest.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncGenerator[None, None]:
    """Dispose the shared asyncpg engine before each test's event loop closes."""
    yield
    await close_engine()


async def _ensure_seeded() -> None:
    await close_engine()
    session_factory = get_session_maker()
    async with session_factory() as session, session.begin():
        await seed_all(session)


@pytest.mark.asyncio
async def test_get_valuations_returns_seeded_defaults_and_user_flags(
    async_client: AsyncClient,
) -> None:
    """GET /profiles/{key}/valuations returns seeded values with accurate is_user_set."""
    await _ensure_seeded()

    maya_res = await async_client.get("/api/v1/profiles/maya/valuations")
    assert maya_res.status_code == 200
    maya_vals = {v["reward_currency"]["code"]: v for v in maya_res.json()}
    assert maya_vals["NW_CASH"]["cents_per_unit"] == "1.0000"
    assert maya_vals["NW_CASH"]["is_user_set"] is False
    assert maya_vals["NWT_PTS"]["cents_per_unit"] == "1.5000"
    assert maya_vals["NWT_PTS"]["is_user_set"] is True
    assert "SKY_MILES" not in maya_vals


@pytest.mark.asyncio
async def test_put_valuation_creates_updates_and_preserves_other_profiles(
    async_client: AsyncClient,
) -> None:
    """PUT /profiles/{key}/valuations/{currency} creates/updates and sets is_user_set=True."""
    await _ensure_seeded()
    try:
        dev_before = (await async_client.get("/api/v1/profiles/dev/valuations")).json()

        # 1. Create SKY_MILES valuation for maya by currency code
        create_res = await async_client.put(
            "/api/v1/profiles/maya/valuations/SKY_MILES",
            json={"cents_per_unit": "1.7500"},
        )
        assert create_res.status_code == 200
        created = create_res.json()
        assert created["reward_currency"]["code"] == "SKY_MILES"
        assert created["cents_per_unit"] == "1.7500"
        assert created["is_user_set"] is True

        # Verify recommendation now ranks Skyward Explorer instead of unranked
        rec_res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 12500,
                "category_code": "groceries",
                "purchase_date": "2026-08-15",
            },
        )
        assert rec_res.status_code == 200
        assert len(rec_res.json()["unranked"]) == 0
        assert any(c["card_name"] == "Skyward Explorer" for c in rec_res.json()["ranked"])

        # 2. Update seeded default NW_CASH by numeric currency ID -> flips is_user_set=True
        nw_cash_id = next(
            v["reward_currency_id"]
            for v in (await async_client.get("/api/v1/profiles/maya/valuations")).json()
            if v["reward_currency"]["code"] == "NW_CASH"
        )
        upd_res = await async_client.put(
            f"/api/v1/profiles/maya/valuations/{nw_cash_id}",
            json={"cents_per_unit": "1.1000"},
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["cents_per_unit"] == "1.1000"
        assert upd_res.json()["is_user_set"] is True

        # 3. Repeated PUT keeps is_user_set=True and updates value
        upd_2 = await async_client.put(
            "/api/v1/profiles/maya/valuations/NW_CASH",
            json={"cents_per_unit": "1.2000"},
        )
        assert upd_2.status_code == 200
        assert upd_2.json()["cents_per_unit"] == "1.2000"
        assert upd_2.json()["is_user_set"] is True

        # 4. Numeric profile ID resolution works for GET and PUT
        maya_id = (await async_client.get("/api/v1/profiles/maya")).json()["id"]
        get_by_id = await async_client.get(f"/api/v1/profiles/{maya_id}/valuations")
        assert get_by_id.status_code == 200
        put_by_id = await async_client.put(
            f"/api/v1/profiles/{maya_id}/valuations/NWT_PTS",
            json={"cents_per_unit": "1.6000"},
        )
        assert put_by_id.status_code == 200
        assert put_by_id.json()["cents_per_unit"] == "1.6000"
        assert put_by_id.json()["is_user_set"] is True

        # 5. Dev's valuations are completely untouched
        dev_after = (await async_client.get("/api/v1/profiles/dev/valuations")).json()
        assert dev_after == dev_before

        # 6. Resetting maya restores original seeded valuations and is_user_set=False
        reset_res = await async_client.post("/api/v1/profiles/maya/reset")
        assert reset_res.status_code == 200
        maya_after_reset = {
            v["reward_currency"]["code"]: v
            for v in (await async_client.get("/api/v1/profiles/maya/valuations")).json()
        }
        assert maya_after_reset["NW_CASH"]["cents_per_unit"] == "1.0000"
        assert maya_after_reset["NW_CASH"]["is_user_set"] is False
        assert "SKY_MILES" not in maya_after_reset
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_put_valuation_range_validation_and_404s(async_client: AsyncClient) -> None:
    """Range bounds (0 < v <= 10) and unknown profile/currency return 422 / 404."""
    await _ensure_seeded()

    for bad_val in (
        "0",
        "0.0000",
        "0.00001",
        "-1.5",
        "10.0001",
        "11",
        "NaN",
        "Infinity",
        "not-a-number",
    ):
        res = await async_client.put(
            "/api/v1/profiles/maya/valuations/NWT_PTS",
            json={"cents_per_unit": bad_val},
        )
        assert res.status_code == 422, f"Expected 422 for {bad_val}, got {res.status_code}"
        assert res.headers["content-type"].startswith("application/problem+json")

    try:
        # Upper boundary 10.0000 and lower positive 0.0001 succeed
        res_max = await async_client.put(
            "/api/v1/profiles/maya/valuations/NWT_PTS",
            json={"cents_per_unit": "10"},
        )
        assert res_max.status_code == 200
        assert res_max.json()["cents_per_unit"] == "10.0000"

        res_min = await async_client.put(
            "/api/v1/profiles/maya/valuations/NWT_PTS",
            json={"cents_per_unit": "0.0001"},
        )
        assert res_min.status_code == 200
        assert res_min.json()["cents_per_unit"] == "0.0001"
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")

    unknown_prof_get = await async_client.get("/api/v1/profiles/nonexistent/valuations")
    unknown_prof_put = await async_client.put(
        "/api/v1/profiles/nonexistent/valuations/NWT_PTS",
        json={"cents_per_unit": "1.5"},
    )
    unknown_curr_put = await async_client.put(
        "/api/v1/profiles/maya/valuations/UNKNOWN_CURR",
        json={"cents_per_unit": "1.5"},
    )
    assert unknown_prof_get.status_code == 404
    assert unknown_prof_put.status_code == 404
    assert unknown_curr_put.status_code == 404
    assert unknown_curr_put.headers["content-type"].startswith("application/problem+json")
