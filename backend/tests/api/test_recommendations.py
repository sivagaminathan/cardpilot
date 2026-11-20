"""Integration tests for seed loader, recommendation API, and dev fault injection (T29)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import Settings
from app.db import close_engine, get_session_maker
from app.main import create_app
from app.models import (
    CardProduct,
    Category,
    CurrencyValuation,
    EarningRule,
    Merchant,
    Profile,
    ProfileCard,
    RewardCurrency,
    RuleExclusion,
    RuleSource,
    Transaction,
)
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
async def test_seed_all_idempotent_and_recommendation_e2e(
    async_client: AsyncClient,
) -> None:
    """Seeding twice creates no duplicates and /recommendations evaluates real DB rules (AC-2)."""
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
    assert isinstance(data["ranked"][0]["warnings"], list)
    assert any(
        u["card_name"] == "Skyward Explorer" and u["reason"] == "no_valuation"
        for u in data["unranked"]
    )
    assert len(data["global_notes"]) >= 1


@pytest.mark.asyncio
async def test_recommendations_specificity_threshold_and_determinism(
    async_client: AsyncClient,
) -> None:
    """Verify AC-3 specificity, AC-7 min-tx threshold, and AC-13 byte-identical determinism."""
    await _ensure_seeded()

    merchants = (await async_client.get("/api/v1/merchants")).json()
    harbor = next(m for m in merchants if m["name"] == "Harbor Roasters")

    # AC-3: Merchant rule (Harbor Roasters) beats dining category & base rules
    spec_res = await async_client.post(
        "/api/v1/profiles/maya/recommendations",
        json={
            "amount_cents": 5000,
            "category_code": "dining",
            "merchant_id": harbor["id"],
            "purchase_date": "2026-08-15",
        },
    )
    assert spec_res.status_code == 200
    dining_card = next(c for c in spec_res.json()["ranked"] if c["card_name"] == "Dining & Travel")
    assert dining_card["applied"][0]["rule_key"] == "nwtpts.harbor_roasters"

    # AC-7: Per-transaction minimum threshold on travel ($25.00 min on Dining & Travel)
    below_min = await async_client.post(
        "/api/v1/profiles/maya/recommendations",
        json={
            "amount_cents": 2000,
            "category_code": "travel",
            "purchase_date": "2026-08-15",
        },
    )
    assert below_min.status_code == 200
    below_card = next(c for c in below_min.json()["ranked"] if c["card_name"] == "Dining & Travel")
    assert below_card["applied"][0]["rule_key"] == "nwtpts.base"

    above_min_1 = await async_client.post(
        "/api/v1/profiles/maya/recommendations",
        json={
            "amount_cents": 5000,
            "category_code": "travel",
            "purchase_date": "2026-08-15",
        },
    )
    above_min_2 = await async_client.post(
        "/api/v1/profiles/maya/recommendations",
        json={
            "amount_cents": 5000,
            "category_code": "travel",
            "purchase_date": "2026-08-15",
        },
    )
    assert above_min_1.status_code == 200
    above_card = next(
        c for c in above_min_1.json()["ranked"] if c["card_name"] == "Dining & Travel"
    )
    assert above_card["applied"][0]["rule_key"] == "nwtpts.travel_min25"
    # AC-13: Byte-identical JSON on identical requests
    assert above_min_1.text == above_min_2.text


@pytest.mark.asyncio
async def test_recommendations_cap_straddle_exhausted_and_valuation_reorder(
    async_client: AsyncClient,
) -> None:
    """Verify AC-5 cap straddle/exhaustion and AC-9 valuation update reordering via HTTP."""
    await _ensure_seeded()
    try:
        session_factory = get_session_maker()
        async with session_factory() as session, session.begin():
            maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
            groceries = await session.scalar(select(Category).where(Category.code == "groceries"))
            assert maya is not None and groceries is not None
            grocery_card = await session.scalar(
                select(ProfileCard).where(
                    ProfileCard.profile_id == maya.id,
                    ProfileCard.nickname == "Grocery 5x",
                )
            )
            assert grocery_card is not None
            # $450.00 prior spend against $500.00 quarterly cap
            session.add(
                Transaction(
                    profile_id=maya.id,
                    profile_card_id=grocery_card.id,
                    amount_cents=45000,
                    category_id=groceries.id,
                    occurred_on=date(2026, 8, 1),
                )
            )

        # AC-5 straddle: $100 purchase -> $50 at 5x (250) + $50 at 1x (50) = 300
        straddle_res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "groceries",
                "purchase_date": "2026-08-15",
            },
        )
        assert straddle_res.status_code == 200
        g_card = next(c for c in straddle_res.json()["ranked"] if c["card_name"] == "Grocery 5x")
        assert g_card["reward_units"] == "300"
        assert len(g_card["applied"]) == 2

        # Add $50 more to exhaust the $500 cap -> 100% fallback to 1x base
        async with session_factory() as session, session.begin():
            maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
            groceries = await session.scalar(select(Category).where(Category.code == "groceries"))
            assert maya is not None and groceries is not None
            grocery_card = await session.scalar(
                select(ProfileCard).where(
                    ProfileCard.profile_id == maya.id,
                    ProfileCard.nickname == "Grocery 5x",
                )
            )
            assert grocery_card is not None
            session.add(
                Transaction(
                    profile_id=maya.id,
                    profile_card_id=grocery_card.id,
                    amount_cents=5000,
                    category_id=groceries.id,
                    occurred_on=date(2026, 8, 10),
                )
            )

        exhausted_res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "groceries",
                "purchase_date": "2026-08-15",
            },
        )
        assert exhausted_res.status_code == 200
        g_exh = next(c for c in exhausted_res.json()["ranked"] if c["card_name"] == "Grocery 5x")
        assert g_exh["reward_units"] == "100"
        assert g_exh["applied"][0]["rule_key"] == "verdant.base"

        # AC-9: Setting SKY_MILES valuation to 10.0 moves Skyward Explorer to #1 ranked
        val_res = await async_client.put(
            "/api/v1/profiles/maya/valuations/SKY_MILES",
            json={"cents_per_unit": "10.0000"},
        )
        assert val_res.status_code == 200
        reordered = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "travel",
                "purchase_date": "2026-08-15",
            },
        )
        assert reordered.status_code == 200
        assert reordered.json()["ranked"][0]["card_name"] == "Skyward Explorer"
        assert reordered.json()["unranked"] == []
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_recommendations_exclusions_and_effective_date_ineligible(
    async_client: AsyncClient,
) -> None:
    """Verify AC-4 exclusions and AC-6 effective-date boundaries / ineligible through HTTP."""
    await _ensure_seeded()
    run_tag = uuid4().hex[:8]
    session_factory = get_session_maker()

    async with session_factory() as session, session.begin():
        dining = await session.scalar(select(Category).where(Category.code == "dining"))
        groceries = await session.scalar(select(Category).where(Category.code == "groceries"))
        cash = await session.scalar(select(RewardCurrency).where(RewardCurrency.code == "NW_CASH"))
        source = await session.scalar(select(RuleSource).order_by(RuleSource.id))
        assert dining and groceries and cash and source

        product = CardProduct(
            issuer_name=f"T29 Issuer {run_tag}",
            name=f"T29 Exclusion Product {run_tag}",
            reward_currency_id=cash.id,
            annual_fee_cents=0,
            network_label="TestNet",
        )
        session.add(product)
        await session.flush()

        # Base rule effective only from 2026-06-01 (before that -> ineligible)
        session.add(
            EarningRule(
                rule_key=f"t29.base.{run_tag}",
                version=1,
                card_product_id=product.id,
                reward_currency_id=cash.id,
                scope_type="base",
                multiplier=Decimal("1.0000"),
                effective_from=date(2026, 6, 1),
                source_id=source.id,
                last_reviewed_on=date(2026, 6, 1),
            )
        )
        # Dining 4x rule that excludes merchant "Excluded Bistro"
        excluded_merch = Merchant(name=f"Excluded Bistro {run_tag}", tags=[])
        session.add(excluded_merch)
        await session.flush()

        dining_rule = EarningRule(
            rule_key=f"t29.dining.{run_tag}",
            version=1,
            card_product_id=product.id,
            reward_currency_id=cash.id,
            scope_type="category",
            category_id=dining.id,
            multiplier=Decimal("4.0000"),
            effective_from=date(2026, 6, 1),
            source_id=source.id,
            last_reviewed_on=date(2026, 6, 1),
        )
        session.add(dining_rule)
        await session.flush()
        session.add(
            RuleExclusion(
                rule_id=dining_rule.id,
                exclusion_type="merchant",
                target_merchant_id=excluded_merch.id,
                reason="Merchant excluded by T29 test",
            )
        )

        profile = Profile(
            slug=f"t29_prof_{run_tag}",
            display_name="T29 Test Profile",
            is_demo=False,
        )
        session.add(profile)
        await session.flush()
        session.add(
            ProfileCard(
                profile_id=profile.id,
                card_product_id=product.id,
                nickname="T29 Card",
                is_active=True,
            )
        )
        session.add(
            CurrencyValuation(
                profile_id=profile.id,
                reward_currency_id=cash.id,
                cents_per_unit=Decimal("1.0000"),
                is_user_set=True,
            )
        )
        slug = profile.slug
        merch_id = excluded_merch.id
        profile_id = profile.id
        product_id = product.id
        dining_rule_id = dining_rule.id

    try:
        # AC-6: Purchase before effective_from -> ineligible
        inelig_res = await async_client.post(
            f"/api/v1/profiles/{slug}/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "dining",
                "purchase_date": "2026-05-31",
            },
        )
        assert inelig_res.status_code == 200
        assert inelig_res.json()["ranked"] == []
        assert len(inelig_res.json()["ineligible"]) == 1
        assert inelig_res.json()["ineligible"][0]["reason"] == "no_effective_rule"

        # AC-4: Exclusion on dining rule falls back to 1x base rule
        excl_res = await async_client.post(
            f"/api/v1/profiles/{slug}/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "dining",
                "merchant_id": merch_id,
                "purchase_date": "2026-06-01",
            },
        )
        assert excl_res.status_code == 200
        assert excl_res.json()["ranked"][0]["reward_units"] == "100"
        assert excl_res.json()["ranked"][0]["applied"][0]["rule_key"] == f"t29.base.{run_tag}"
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(delete(Profile).where(Profile.id == profile_id))
            await session.execute(
                delete(RuleExclusion).where(RuleExclusion.rule_id == dining_rule_id)
            )
            await session.execute(
                delete(EarningRule).where(EarningRule.card_product_id == product_id)
            )
            await session.execute(delete(CardProduct).where(CardProduct.id == product_id))
            await session.execute(delete(Merchant).where(Merchant.id == merch_id))


@pytest.mark.asyncio
async def test_recommendations_card_ids_subset_and_error_handling(
    async_client: AsyncClient,
) -> None:
    """Verify card_ids subset filtering, cross-profile rejection, and RFC 9457 error handling."""
    await _ensure_seeded()

    maya_cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
    dev_cards = (await async_client.get("/api/v1/profiles/dev/cards")).json()
    subset_ids = [maya_cards[0]["id"], maya_cards[1]["id"]]

    subset_res = await async_client.post(
        "/api/v1/profiles/maya/recommendations",
        json={
            "amount_cents": 10000,
            "category_code": "dining",
            "purchase_date": "2026-08-15",
            "card_ids": subset_ids,
        },
    )
    assert subset_res.status_code == 200
    returned_ids = {
        c["profile_card_id"]
        for c in (
            subset_res.json()["ranked"]
            + subset_res.json()["unranked"]
            + subset_res.json()["ineligible"]
        )
    }
    assert returned_ids == set(subset_ids)

    # Cross-profile and unknown card_ids -> 404
    for bad_ids in ([999999], [dev_cards[0]["id"]]):
        res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "dining",
                "card_ids": bad_ids,
            },
        )
        assert res.status_code == 404
        assert res.headers["content-type"].startswith("application/problem+json")

    # Invalid card_ids (empty, non-positive, boolean, duplicate) and amount_cents -> 422
    for bad_payload in (
        {"amount_cents": 10000, "category_code": "dining", "card_ids": []},
        {"amount_cents": 10000, "category_code": "dining", "card_ids": [0]},
        {"amount_cents": 10000, "category_code": "dining", "card_ids": [True]},
        {
            "amount_cents": 10000,
            "category_code": "dining",
            "card_ids": [subset_ids[0], subset_ids[0]],
        },
        {"amount_cents": 0, "category_code": "dining"},
    ):
        res = await async_client.post("/api/v1/profiles/maya/recommendations", json=bad_payload)
        assert res.status_code == 422
        assert res.headers["content-type"].startswith("application/problem+json")

    # Unknown profile -> 404; unknown category / merchant -> 400
    assert (
        await async_client.post(
            "/api/v1/profiles/unknown-slug/recommendations",
            json={"amount_cents": 1000, "category_code": "dining"},
        )
    ).status_code == 404
    assert (
        await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={"amount_cents": 1000, "category_code": "unknown_cat"},
        )
    ).status_code == 400
    assert (
        await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={"amount_cents": 1000, "category_code": "dining", "merchant_id": 999999},
        )
    ).status_code == 400


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
