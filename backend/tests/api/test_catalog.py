"""PostgreSQL integration tests for reference catalog, profile, and card CRUD APIs (T26)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import close_engine, get_session_maker
from app.models import Profile, ProfileCard
from app.seeds.loader import seed_all
from app.services import catalog as catalog_service


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
async def test_reference_endpoints_return_seeded_catalog(async_client: AsyncClient) -> None:
    """Merchants, currencies, card products, rules, and benefits return seeded records."""
    await _ensure_seeded()

    merchants_res = await async_client.get("/api/v1/merchants")
    assert merchants_res.status_code == 200
    merchants = merchants_res.json()
    assert len(merchants) >= 1
    assert any(m["name"] == "Harbor Roasters" for m in merchants)

    currencies_res = await async_client.get("/api/v1/reward-currencies")
    assert currencies_res.status_code == 200
    currencies = currencies_res.json()
    assert {"NW_CASH", "NWT_PTS", "SKY_MILES"}.issubset({c["code"] for c in currencies})
    assert all(isinstance(c["default_cents_per_unit"], str) for c in currencies)

    products_res = await async_client.get("/api/v1/card-products")
    assert products_res.status_code == 200
    products = products_res.json()
    assert len(products) >= 6
    first_product_id = products[0]["id"]

    rules_res = await async_client.get(f"/api/v1/card-products/{first_product_id}/rules")
    assert rules_res.status_code == 200
    rules = rules_res.json()
    assert len(rules) >= 1
    assert "source" in rules[0]
    assert "last_reviewed_on" in rules[0]["source"]
    assert isinstance(rules[0]["multiplier"], str)

    benefits_res = await async_client.get(f"/api/v1/card-products/{first_product_id}/benefits")
    assert benefits_res.status_code == 200
    assert isinstance(benefits_res.json(), list)


@pytest.mark.asyncio
async def test_card_product_not_found_returns_404(async_client: AsyncClient) -> None:
    """Rules and benefits endpoints return RFC 9457 404 for unknown card products."""
    await _ensure_seeded()
    rules_res = await async_client.get("/api/v1/card-products/999999/rules")
    benefits_res = await async_client.get("/api/v1/card-products/999999/benefits")
    assert rules_res.status_code == 404
    assert benefits_res.status_code == 404
    assert rules_res.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_get_single_profile_by_slug_and_id(async_client: AsyncClient) -> None:
    """GET /profiles/{profile_key} resolves by slug and ID and returns 404 when missing."""
    await _ensure_seeded()
    by_slug = await async_client.get("/api/v1/profiles/maya")
    assert by_slug.status_code == 200
    profile_id = by_slug.json()["id"]

    by_id = await async_client.get(f"/api/v1/profiles/{profile_id}")
    assert by_id.status_code == 200
    assert by_id.json() == by_slug.json()

    missing = await async_client.get("/api/v1/profiles/nonexistent")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_profile_cards_crud_and_scoping(async_client: AsyncClient) -> None:
    """Profile card list, create, update, delete, duplicate, and cross-profile scoping work."""
    await _ensure_seeded()
    try:
        list_res = await async_client.get("/api/v1/profiles/maya/cards")
        assert list_res.status_code == 200
        assert len(list_res.json()) == 4

        products = (await async_client.get("/api/v1/card-products")).json()
        product_id = products[0]["id"]

        # Create
        create_res = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={
                "card_product_id": product_id,
                "nickname": "T26 Test Card",
                "opened_on": "2026-01-15",
            },
        )
        assert create_res.status_code == 201
        created = create_res.json()
        created_id = created["id"]
        assert created["nickname"] == "T26 Test Card"
        assert created["is_active"] is True

        # Duplicate on same profile -> 409
        dup_res = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={"card_product_id": product_id, "nickname": "T26 Test Card"},
        )
        assert dup_res.status_code == 409

        # Blank nickname -> 422
        blank_res = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={"card_product_id": product_id, "nickname": "   "},
        )
        assert blank_res.status_code == 422

        # Unknown product -> 404
        bad_prod = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={"card_product_id": 999999, "nickname": "Missing Product"},
        )
        assert bad_prod.status_code == 404

        # Cross-profile scoping: dev cannot patch or delete maya's card
        cross_patch = await async_client.patch(
            f"/api/v1/profiles/dev/cards/{created_id}",
            json={"nickname": "Hijacked"},
        )
        cross_delete = await async_client.delete(f"/api/v1/profiles/dev/cards/{created_id}")
        assert cross_patch.status_code == 404
        assert cross_delete.status_code == 404

        # Valid patch on maya
        patch_res = await async_client.patch(
            f"/api/v1/profiles/maya/cards/{created_id}",
            json={"nickname": "T26 Renamed Card", "is_active": False},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["nickname"] == "T26 Renamed Card"
        assert patch_res.json()["is_active"] is False

        # Valid delete on maya
        del_res = await async_client.delete(f"/api/v1/profiles/maya/cards/{created_id}")
        assert del_res.status_code == 204

        after_del = await async_client.get("/api/v1/profiles/maya/cards")
        assert len(after_del.json()) == 4
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_db_unique_constraint_enforced_and_handled_on_bypass(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB unique constraint rejects duplicates directly and maps race-condition 409 cleanly."""
    await _ensure_seeded()
    session_factory = get_session_maker()

    try:
        # 1. Direct DB insert of duplicate (profile_id, card_product_id, nickname) fails
        async with session_factory() as session:
            maya = await session.scalar(select(Profile).where(Profile.slug == "maya"))
            assert maya is not None
            existing = await session.scalar(
                select(ProfileCard)
                .where(ProfileCard.profile_id == maya.id)
                .order_by(ProfileCard.id)
            )
            assert existing is not None
            dup_product_id = existing.card_product_id
            dup_nickname = existing.nickname
            session.add(
                ProfileCard(
                    profile_id=maya.id,
                    card_product_id=dup_product_id,
                    nickname=dup_nickname,
                    is_active=True,
                )
            )
            with pytest.raises(IntegrityError) as exc_info:
                await session.flush()
            assert "uq_profile_cards_profile_product_nickname" in str(exc_info.value)
            await session.rollback()

        # 2. Bypass application-level duplicate pre-check to simulate concurrent race
        orig_scalar = None

        async def _always_none_on_dup_check(self, statement, *args, **kwargs):
            text_sql = str(statement)
            if "FROM profile_cards" in text_sql and "profile_cards.nickname =" in text_sql:
                return None
            return await orig_scalar(self, statement, *args, **kwargs)

        from sqlalchemy.ext.asyncio import AsyncSession

        orig_scalar = AsyncSession.scalar
        monkeypatch.setattr(AsyncSession, "scalar", _always_none_on_dup_check)

        race_res = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={"card_product_id": dup_product_id, "nickname": dup_nickname},
        )
        assert race_res.status_code == 409
        assert race_res.headers["content-type"].startswith("application/problem+json")
        assert race_res.json()["status"] == 409

        # Restore AsyncSession.scalar and verify API/DB remain usable
        monkeypatch.undo()
        ok_list = await async_client.get("/api/v1/profiles/maya/cards")
        assert ok_list.status_code == 200
        assert len(ok_list.json()) == 4

        ok_create = await async_client.post(
            "/api/v1/profiles/maya/cards",
            json={"card_product_id": dup_product_id, "nickname": "Post-409 Card"},
        )
        assert ok_create.status_code == 201
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


def test_unrelated_integrity_error_not_treated_as_duplicate() -> None:
    """Unrelated IntegrityError (e.g. FK/CHECK violation) is not misclassified as duplicate."""
    unrelated = IntegrityError("INSERT ...", {}, Exception("ck_profile_cards_other"))
    assert catalog_service._is_duplicate_profile_card_error(unrelated) is False
