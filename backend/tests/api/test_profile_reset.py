"""Integration tests for POST /api/v1/profiles/{profile_key}/reset (T25)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import close_engine, get_session_maker
from app.models import (
    BenefitDefinition,
    BenefitUsage,
    CardProduct,
    Category,
    CurrencyValuation,
    Profile,
    ProfileCard,
    RewardCurrency,
    Transaction,
)
from app.seeds import loader as seed_loader


@pytest.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncGenerator[None, None]:
    """Dispose the shared asyncpg engine before each test's event loop closes."""
    yield
    await close_engine()


async def _ensure_seeded_clean() -> None:
    await close_engine()
    session_factory = get_session_maker()
    async with session_factory() as session, session.begin():
        await seed_loader.seed_all(session)


@pytest.mark.asyncio
async def test_reset_maya_and_dev_and_idempotency(async_client: AsyncClient) -> None:
    """Resetting maya and dev restores seeded counts and is idempotent across repeats."""
    await _ensure_seeded_clean()

    res_maya_1 = await async_client.post("/api/v1/profiles/maya/reset")
    assert res_maya_1.status_code == 200
    body_1 = res_maya_1.json()
    assert body_1["status"] == "reset"
    assert body_1["profile"]["slug"] == "maya"
    assert body_1["cards_restored"] == 4
    assert body_1["valuations_restored"] == 2

    res_maya_2 = await async_client.post("/api/v1/profiles/maya/reset")
    assert res_maya_2.status_code == 200
    assert res_maya_2.json() == body_1

    res_dev = await async_client.post("/api/v1/profiles/dev/reset")
    assert res_dev.status_code == 200
    body_dev = res_dev.json()
    assert body_dev["status"] == "reset"
    assert body_dev["profile"]["slug"] == "dev"
    assert body_dev["cards_restored"] == 3
    assert body_dev["valuations_restored"] == 3


@pytest.mark.asyncio
async def test_reset_clears_user_changes_and_preserves_other_profiles(
    async_client: AsyncClient,
) -> None:
    """Resetting maya removes user-added cards/txs/usages while preserving dev and catalog."""
    await _ensure_seeded_clean()
    session_factory = get_session_maker()

    async with session_factory() as session, session.begin():
        maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
        dev = await session.scalar(select(Profile).where(Profile.slug == "dev"))
        assert maya is not None and dev is not None

        product = await session.scalar(select(CardProduct).order_by(CardProduct.id))
        category = await session.scalar(select(Category).order_by(Category.id))
        sky_miles = await session.scalar(
            select(RewardCurrency).where(RewardCurrency.code == "SKY_MILES")
        )
        benefit = await session.scalar(select(BenefitDefinition).order_by(BenefitDefinition.id))
        assert product and category and sky_miles and benefit

        # Mutate maya: add extra card, transaction, benefit usage, and valuation
        extra_maya_card = ProfileCard(
            profile_id=maya.id,
            card_product_id=product.id,
            nickname="User Added Card",
            is_active=True,
        )
        session.add(extra_maya_card)
        await session.flush()

        session.add(
            Transaction(
                profile_id=maya.id,
                profile_card_id=extra_maya_card.id,
                amount_cents=5000,
                category_id=category.id,
                occurred_on=date(2026, 8, 10),
                note="Temp tx",
            )
        )
        session.add(
            BenefitUsage(
                profile_card_id=extra_maya_card.id,
                benefit_definition_id=benefit.id,
                amount_cents=1000,
                used_on=date(2026, 8, 10),
                note="Temp usage",
            )
        )
        session.add(
            CurrencyValuation(
                profile_id=maya.id,
                reward_currency_id=sky_miles.id,
                cents_per_unit=Decimal("2.0000"),
                is_user_set=True,
            )
        )

        # Mutate dev: add a custom card that must survive maya reset
        session.add(
            ProfileCard(
                profile_id=dev.id,
                card_product_id=product.id,
                nickname="Dev Custom Card",
                is_active=True,
            )
        )

    before_products = await _count_rows(CardProduct)

    res = await async_client.post("/api/v1/profiles/maya/reset")
    assert res.status_code == 200
    assert res.json()["cards_restored"] == 4
    assert res.json()["valuations_restored"] == 2

    try:
        async with session_factory() as session:
            maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
            dev = await session.scalar(select(Profile).where(Profile.slug == "dev"))
            assert maya is not None and dev is not None

            maya_cards = (
                await session.scalars(select(ProfileCard).where(ProfileCard.profile_id == maya.id))
            ).all()
            maya_txs = (
                await session.scalars(select(Transaction).where(Transaction.profile_id == maya.id))
            ).all()
            maya_vals = (
                await session.scalars(
                    select(CurrencyValuation).where(CurrencyValuation.profile_id == maya.id)
                )
            ).all()
            dev_custom = await session.scalar(
                select(ProfileCard).where(
                    ProfileCard.profile_id == dev.id,
                    ProfileCard.nickname == "Dev Custom Card",
                )
            )
            assert len(maya_cards) == 4
            assert len(maya_txs) == 0
            assert len(maya_vals) == 2
            assert dev_custom is not None
            assert await _count_rows(CardProduct) == before_products
    finally:
        await async_client.post("/api/v1/profiles/dev/reset")


async def _count_rows(model: type) -> int:
    session_factory = get_session_maker()
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(model))
        return int(count or 0)


@pytest.mark.asyncio
async def test_reset_unknown_profile_returns_404(async_client: AsyncClient) -> None:
    """Unknown profile returns RFC 9457 404 problem details."""
    await _ensure_seeded_clean()
    res = await async_client.post("/api/v1/profiles/unknown-profile/reset")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["status"] == 404


@pytest.mark.asyncio
async def test_reset_rolls_back_on_failure(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An error during reset rolls back deletions atomically."""
    await _ensure_seeded_clean()
    session_factory = get_session_maker()

    async def failing_reset(session, profile):
        await seed_loader.reset_profile_to_seed.__wrapped__(session, profile) if hasattr(
            seed_loader.reset_profile_to_seed, "__wrapped__"
        ) else None
        raise RuntimeError("simulated mid-transaction failure")

    # Actually delete maya cards inside reset, then raise before commit
    orig_reset = seed_loader.reset_profile_to_seed

    async def delete_then_fail(session, profile):
        await orig_reset(session, profile)
        raise RuntimeError("simulated failure before commit")

    monkeypatch.setattr("app.services.recommendations.reset_profile_to_seed", delete_then_fail)

    with pytest.raises(RuntimeError, match="simulated failure before commit"):
        await async_client.post("/api/v1/profiles/maya/reset")

    async with session_factory() as session:
        maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
        assert maya is not None
        maya_cards = (
            await session.scalars(select(ProfileCard).where(ProfileCard.profile_id == maya.id))
        ).all()
        assert len(maya_cards) == 4
