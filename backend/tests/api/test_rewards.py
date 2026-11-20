"""PostgreSQL integration tests for T34 rewards summary endpoint (AC-10, FR-27, FR-29)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db import close_engine, get_session_maker
from app.models import CurrencyValuation, Profile, RewardCurrency, TransactionRewardCalc
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
async def test_rewards_summary_empty_profile_and_unknown_profile(
    async_client: AsyncClient,
) -> None:
    """Empty profile returns empty currencies list and 0 estimated USD; unknown returns 404."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")

    res = await async_client.get("/api/v1/profiles/maya/rewards/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["profile_slug"] == "maya"
    assert body["currencies"] == []
    assert body["estimated_total_usd_cents"] == 0
    assert body["excluded_unvalued_currency_codes"] == []
    assert body["limitation_message"] is None

    not_found = await async_client.get("/api/v1/profiles/no-such-profile/rewards/summary")
    assert not_found.status_code == 404
    assert not_found.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_rewards_summary_multi_currency_unvalued_and_valuation_update(
    async_client: AsyncClient,
) -> None:
    """Per-currency aggregation, unvalued exclusion, valuation update, snapshot immutability."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    await async_client.post("/api/v1/profiles/dev/reset")
    try:
        maya_cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        dev_cards = (await async_client.get("/api/v1/profiles/dev/cards")).json()

        nwcash_card = next(
            c for c in maya_cards if c["card_product"]["name"] == "Northwind Cash Everyday"
        )
        nwtpts_card = next(
            c for c in maya_cards if c["card_product"]["name"] == "Northwind Dining & Travel"
        )
        skymiles_card = next(
            c for c in maya_cards if c["card_product"]["name"] == "Skyward Miles Explorer"
        )

        # Two transactions in NW_CASH (dining 3.5x on $20 = 70, gas 2x on $30 = 60 -> 130)
        tx1 = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": nwcash_card["id"],
                    "amount_cents": 2000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-10",
                },
            )
        ).json()
        await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": nwcash_card["id"],
                "amount_cents": 3000,
                "category_code": "gas",
                "occurred_on": "2026-11-11",
            },
        )
        # One transaction in NWT_PTS (dining 3x on $100 = 300 pts @ 1.5 cents/pt = 450 cents)
        tx_pts = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": nwtpts_card["id"],
                    "amount_cents": 10000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-12",
                },
            )
        ).json()
        # One transaction in SKY_MILES (unvalued for Maya: travel 4x on $50 = 200 miles)
        await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": skymiles_card["id"],
                "amount_cents": 5000,
                "category_code": "travel",
                "occurred_on": "2026-11-12",
            },
        )
        # Another profile's transaction (must NOT leak into Maya's summary)
        await async_client.post(
            "/api/v1/profiles/dev/transactions",
            json={
                "profile_card_id": dev_cards[0]["id"],
                "amount_cents": 10000,
                "category_code": "dining",
                "occurred_on": "2026-11-12",
            },
        )

        summary = (await async_client.get("/api/v1/profiles/maya/rewards/summary")).json()
        by_code = {c["reward_currency_code"]: c for c in summary["currencies"]}
        assert set(by_code) == {"NW_CASH", "NWT_PTS", "SKY_MILES"}

        assert Decimal(by_code["NW_CASH"]["total_reward_units"]) == Decimal("130")
        assert by_code["NW_CASH"]["transaction_count"] == 2
        assert by_code["NW_CASH"]["is_valued"] is True
        assert by_code["NW_CASH"]["valuation_status"] == "valued"
        assert by_code["NW_CASH"]["estimated_value_cents"] == 130

        assert Decimal(by_code["NWT_PTS"]["total_reward_units"]) == Decimal("300")
        assert by_code["NWT_PTS"]["estimated_value_cents"] == 450

        assert Decimal(by_code["SKY_MILES"]["total_reward_units"]) == Decimal("200")
        assert by_code["SKY_MILES"]["is_valued"] is False
        assert by_code["SKY_MILES"]["valuation_status"] == "unvalued"
        assert by_code["SKY_MILES"]["current_cents_per_unit"] is None
        assert by_code["SKY_MILES"]["estimated_value_cents"] is None
        assert by_code["SKY_MILES"]["limitation_note"] is not None

        # Total includes ONLY valued currencies (130 + 450 = 580)
        assert summary["estimated_total_usd_cents"] == 580
        assert summary["excluded_unvalued_currency_codes"] == ["SKY_MILES"]
        assert summary["limitation_message"] is not None
        assert "SKY_MILES" in summary["limitation_message"]

        # Update Maya's NWT_PTS valuation from 1.5 -> 2.0 cents/unit
        put_res = await async_client.put(
            "/api/v1/profiles/maya/valuations/NWT_PTS",
            json={"cents_per_unit": "2.0000"},
        )
        assert put_res.status_code == 200

        updated = (await async_client.get("/api/v1/profiles/maya/rewards/summary")).json()
        updated_by_code = {c["reward_currency_code"]: c for c in updated["currencies"]}
        # Units are UNCHANGED; estimated value updates (300 * 2.0 = 600; total = 130 + 600 = 730)
        assert Decimal(updated_by_code["NWT_PTS"]["total_reward_units"]) == Decimal("300")
        assert updated_by_code["NWT_PTS"]["estimated_value_cents"] == 600
        assert updated["estimated_total_usd_cents"] == 730

        # Snapshot valuation-at-calculation remains unchanged (1.5000)
        session_factory = get_session_maker()
        async with session_factory() as session:
            db_calc = await session.scalar(
                select(TransactionRewardCalc).where(
                    TransactionRewardCalc.transaction_id == tx_pts["id"]
                )
            )
            assert db_calc is not None
            assert db_calc.valuation_cents_per_unit_used == Decimal("1.5000")
            assert db_calc.estimated_value_cents == 450
            assert tx1["reward_calc"]["valuation_cents_per_unit_used"] == "1.0000"
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
        await async_client.post("/api/v1/profiles/dev/reset")


@pytest.mark.asyncio
async def test_rewards_summary_rounding_and_zero_units(
    async_client: AsyncClient,
) -> None:
    """Summary uses ROUND_HALF_EVEN for Decimal precision and handles zero-unit snapshots."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    try:
        maya_cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        nwtpts_card = next(
            c for c in maya_cards if c["card_product"]["name"] == "Northwind Dining & Travel"
        )
        nwcash_card = next(
            c for c in maya_cards if c["card_product"]["name"] == "Northwind Cash Everyday"
        )

        # Ineligible transaction (2020-01-01) -> 0.0000 reward units in NW_CASH
        zero_tx = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": nwcash_card["id"],
                "amount_cents": 2500,
                "category_code": "dining",
                "occurred_on": "2020-01-01",
            },
        )
        assert zero_tx.status_code == 201
        assert Decimal(zero_tx.json()["reward_calc"]["reward_units"]) == Decimal("0")

        # 100 cents ($1.00) * 1.0x = 1 NWT_PTS; valuation 1.5 -> 1.5 -> 2 (ROUND_HALF_EVEN)
        await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": nwtpts_card["id"],
                "amount_cents": 100,
                "category_code": "groceries",
                "occurred_on": "2026-11-15",
            },
        )

        # Verify Maya's valuation for NWT_PTS is 1.5000 -> 1 * 1.5 = 1.5 -> rounds half-to-even = 2
        summary = (await async_client.get("/api/v1/profiles/maya/rewards/summary")).json()
        by_code = {c["reward_currency_code"]: c for c in summary["currencies"]}

        assert Decimal(by_code["NW_CASH"]["total_reward_units"]) == Decimal("0")
        assert by_code["NW_CASH"]["estimated_value_cents"] == 0
        assert Decimal(by_code["NWT_PTS"]["total_reward_units"]) == Decimal("1")
        assert by_code["NWT_PTS"]["estimated_value_cents"] == 2
        assert summary["estimated_total_usd_cents"] == 2

        # Also test 2.5 -> 2 (round half to even) when 2 units * 1.2500 = 2.5
        session_factory = get_session_maker()
        async with session_factory() as session, session.begin():
            maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
            nwt = await session.scalar(
                select(RewardCurrency).where(RewardCurrency.code == "NWT_PTS")
            )
            assert maya is not None and nwt is not None
            val = await session.scalar(
                select(CurrencyValuation).where(
                    CurrencyValuation.profile_id == maya.id,
                    CurrencyValuation.reward_currency_id == nwt.id,
                )
            )
            assert val is not None
            val.cents_per_unit = Decimal("2.5000")

        # 1 unit * 2.5000 = 2.5 -> ROUND_HALF_EVEN = 2
        summary_even = (await async_client.get("/api/v1/profiles/maya/rewards/summary")).json()
        pts_even = next(
            c for c in summary_even["currencies"] if c["reward_currency_code"] == "NWT_PTS"
        )
        assert pts_even["estimated_value_cents"] == 2
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
