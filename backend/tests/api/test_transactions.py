"""PostgreSQL integration tests for T31 transaction endpoints & immutable snapshots."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import close_engine, get_session_maker
from app.engine import ENGINE_VERSION
from app.models import CalcRuleReference, Transaction, TransactionRewardCalc
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
async def test_post_transaction_persists_snapshot_and_rule_references(
    async_client: AsyncClient,
) -> None:
    """POST creates transaction, immutable TransactionRewardCalc, and CalcRuleReference rows."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    try:
        cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        dining_card = next(
            c for c in cards if c["card_product"]["name"] == "Northwind Dining & Travel"
        )

        rec_res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "dining",
                "purchase_date": "2026-11-15",
                "card_ids": [dining_card["id"]],
            },
        )
        assert rec_res.status_code == 200
        expected_item = rec_res.json()["ranked"][0]

        post_res = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": dining_card["id"],
                "amount_cents": 10000,
                "category_code": "dining",
                "merchant_text": "Harbor Bistro",
                "occurred_on": "2026-11-15",
                "note": "Team dinner",
            },
        )
        assert post_res.status_code == 201
        body = post_res.json()
        calc = body["reward_calc"]

        assert calc["engine_version"] == ENGINE_VERSION
        assert calc["reward_currency"] == expected_item["reward_currency"]
        assert Decimal(calc["reward_units"]) == Decimal(expected_item["reward_units"])
        assert calc["estimated_value_cents"] == expected_item["estimated_value_cents"]
        assert calc["valuation_cents_per_unit_used"] is not None
        assert calc["trace"]["status"] == "ranked"
        assert len(calc["trace"]["applied_portions"]) >= 1
        assert len(calc["applied_rule_ids"]) >= 1

        session_factory = get_session_maker()
        async with session_factory() as session:
            db_tx = await session.scalar(select(Transaction).where(Transaction.id == body["id"]))
            db_calc = await session.scalar(
                select(TransactionRewardCalc).where(
                    TransactionRewardCalc.transaction_id == body["id"]
                )
            )
            refs = (
                await session.scalars(
                    select(CalcRuleReference).where(CalcRuleReference.calc_id == calc["id"])
                )
            ).all()
            assert db_tx is not None
            assert db_calc is not None
            assert db_calc.engine_version == ENGINE_VERSION
            assert sorted(r.rule_id for r in refs) == calc["applied_rule_ids"]
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_post_transaction_no_applicable_rule_persists_ineligible_snapshot(
    async_client: AsyncClient,
) -> None:
    """When no rule is effective on occurred_on, an ineligible snapshot is still persisted."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    try:
        cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        card_id = cards[0]["id"]

        res = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": card_id,
                "amount_cents": 2500,
                "category_code": "dining",
                "occurred_on": "2020-01-01",
            },
        )
        assert res.status_code == 201
        calc = res.json()["reward_calc"]
        assert Decimal(calc["reward_units"]) == Decimal("0")
        assert calc["trace"]["status"] == "ineligible"
        assert calc["trace"]["rejection_reason"] == "no_effective_rule"
        assert calc["trace"]["applied_portions"] == []
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_get_transactions_filters_ordering_and_profile_isolation(
    async_client: AsyncClient,
) -> None:
    """GET supports card/category/inclusive-date filters, deterministic order, and isolation."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    await async_client.post("/api/v1/profiles/dev/reset")
    try:
        maya_cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        dev_cards = (await async_client.get("/api/v1/profiles/dev/cards")).json()

        c1 = maya_cards[0]["id"]
        c2 = maya_cards[1]["id"]

        tx1 = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": c1,
                    "amount_cents": 1500,
                    "category_code": "dining",
                    "occurred_on": "2026-11-10",
                },
            )
        ).json()
        tx2 = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": c1,
                    "amount_cents": 2000,
                    "category_code": "groceries",
                    "occurred_on": "2026-11-12",
                },
            )
        ).json()
        tx3 = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": c2,
                    "amount_cents": 3000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-12",
                },
            )
        ).json()
        dev_tx = (
            await async_client.post(
                "/api/v1/profiles/dev/transactions",
                json={
                    "profile_card_id": dev_cards[0]["id"],
                    "amount_cents": 5000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-12",
                },
            )
        ).json()

        # Deterministic ordering: occurred_on DESC, id DESC
        all_maya = (await async_client.get("/api/v1/profiles/maya/transactions")).json()
        assert [t["id"] for t in all_maya] == [tx3["id"], tx2["id"], tx1["id"]]
        assert dev_tx["id"] not in {t["id"] for t in all_maya}

        # Filter by profile_card_id
        by_card = (
            await async_client.get(
                "/api/v1/profiles/maya/transactions",
                params={"profile_card_id": c2},
            )
        ).json()
        assert [t["id"] for t in by_card] == [tx3["id"]]

        # Filter by category_code
        by_cat = (
            await async_client.get(
                "/api/v1/profiles/maya/transactions",
                params={"category_code": "groceries"},
            )
        ).json()
        assert [t["id"] for t in by_cat] == [tx2["id"]]

        # Inclusive date boundaries
        by_dates = (
            await async_client.get(
                "/api/v1/profiles/maya/transactions",
                params={"date_from": "2026-11-10", "date_to": "2026-11-10"},
            )
        ).json()
        assert [t["id"] for t in by_dates] == [tx1["id"]]

        # Invalid date range returns 422
        bad_range = await async_client.get(
            "/api/v1/profiles/maya/transactions",
            params={"date_from": "2026-11-15", "date_to": "2026-11-10"},
        )
        assert bad_range.status_code == 422
        assert bad_range.headers["content-type"].startswith("application/problem+json")
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
        await async_client.post("/api/v1/profiles/dev/reset")


@pytest.mark.asyncio
async def test_delete_frees_cap_and_preserves_other_snapshots(
    async_client: AsyncClient,
) -> None:
    """DELETE cascades snapshot/refs, frees cap for new recs, and leaves other snapshots intact."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    try:
        cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        grocery_card = next(
            c for c in cards if c["card_product"]["name"] == "Verdant Grocery Specialist"
        )
        cid = grocery_card["id"]

        # Exhaust $1,500 quarterly grocery cap on cascade_everyday
        tx_cap = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": cid,
                    "amount_cents": 150000,
                    "category_code": "groceries",
                    "occurred_on": "2026-11-05",
                },
            )
        ).json()
        tx_other = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": cid,
                    "amount_cents": 10000,
                    "category_code": "groceries",
                    "occurred_on": "2026-11-06",
                },
            )
        ).json()

        rec_exhausted = (
            await async_client.post(
                "/api/v1/profiles/maya/recommendations",
                json={
                    "amount_cents": 10000,
                    "category_code": "groceries",
                    "purchase_date": "2026-11-15",
                    "card_ids": [cid],
                },
            )
        ).json()["ranked"][0]

        del_res = await async_client.delete(f"/api/v1/profiles/maya/transactions/{tx_cap['id']}")
        assert del_res.status_code == 204

        # Freed cap capacity is reflected in subsequent recommendation
        rec_freed = (
            await async_client.post(
                "/api/v1/profiles/maya/recommendations",
                json={
                    "amount_cents": 10000,
                    "category_code": "groceries",
                    "purchase_date": "2026-11-15",
                    "card_ids": [cid],
                },
            )
        ).json()["ranked"][0]
        assert Decimal(rec_freed["reward_units"]) > Decimal(rec_exhausted["reward_units"])

        # Other transaction's snapshot was NOT recomputed
        remaining = (await async_client.get("/api/v1/profiles/maya/transactions")).json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == tx_other["id"]
        assert remaining[0]["reward_calc"] == tx_other["reward_calc"]

        # DB snapshot and rule references for deleted tx are gone
        session_factory = get_session_maker()
        async with session_factory() as session:
            calc_count = await session.scalar(
                select(func.count(TransactionRewardCalc.id)).where(
                    TransactionRewardCalc.transaction_id == tx_cap["id"]
                )
            )
            assert calc_count == 0
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_backdated_and_inactive_card_transactions(
    async_client: AsyncClient,
) -> None:
    """Backdated txs use historical spend without altering later snapshots; inactive cards work."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    try:
        cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        grocery_card = next(
            c for c in cards if c["card_product"]["name"] == "Verdant Grocery Specialist"
        )
        cid = grocery_card["id"]

        # Record a later transaction first (no prior spend)
        later_tx = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": cid,
                    "amount_cents": 10000,
                    "category_code": "groceries",
                    "occurred_on": "2026-11-20",
                },
            )
        ).json()

        # Backdated transaction that consumes $1,450 of the $1,500 cap as of 2026-11-10
        backdated_tx = (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": cid,
                    "amount_cents": 145000,
                    "category_code": "groceries",
                    "occurred_on": "2026-11-10",
                },
            )
        ).json()
        assert Decimal(backdated_tx["reward_calc"]["reward_units"]) > Decimal("0")

        # Later transaction's snapshot remains unchanged
        txs = (await async_client.get("/api/v1/profiles/maya/transactions")).json()
        fetched_later = next(t for t in txs if t["id"] == later_tx["id"])
        assert fetched_later["reward_calc"] == later_tx["reward_calc"]

        # Mark card inactive: recommendations exclude it, but POST transaction still succeeds
        patch_res = await async_client.patch(
            f"/api/v1/profiles/maya/cards/{cid}",
            json={"is_active": False},
        )
        assert patch_res.status_code == 200

        rec_res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 5000,
                "category_code": "groceries",
                "purchase_date": "2026-11-15",
                "card_ids": [cid],
            },
        )
        assert rec_res.status_code == 404

        inactive_tx = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": cid,
                "amount_cents": 2500,
                "category_code": "groceries",
                "occurred_on": "2026-11-15",
            },
        )
        assert inactive_tx.status_code == 201
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")


@pytest.mark.asyncio
async def test_transaction_validation_errors_sensitive_guard_and_duplicates(
    async_client: AsyncClient,
) -> None:
    """Validate ownership/ref errors, 422 rules, sensitive guard, 12/20 boundaries, duplicates."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")
    await async_client.post("/api/v1/profiles/dev/reset")
    try:
        maya_cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        dev_cards = (await async_client.get("/api/v1/profiles/dev/cards")).json()
        merchants = (await async_client.get("/api/v1/merchants")).json()
        maya_cid = maya_cards[0]["id"]
        dev_cid = dev_cards[0]["id"]
        merchant_id = merchants[0]["id"]

        # Unknown profile / cross-profile card / missing card -> 404
        assert (
            await async_client.post(
                "/api/v1/profiles/no-such-profile/transactions",
                json={
                    "profile_card_id": maya_cid,
                    "amount_cents": 1000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-15",
                },
            )
        ).status_code == 404
        assert (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": dev_cid,
                    "amount_cents": 1000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-15",
                },
            )
        ).status_code == 404
        assert (
            await async_client.delete("/api/v1/profiles/maya/transactions/999999")
        ).status_code == 404

        # Unknown category / unknown merchant -> 400
        assert (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": maya_cid,
                    "amount_cents": 1000,
                    "category_code": "unknown_cat",
                    "occurred_on": "2026-11-15",
                },
            )
        ).status_code == 400
        assert (
            await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": maya_cid,
                    "amount_cents": 1000,
                    "category_code": "dining",
                    "merchant_id": 999999,
                    "occurred_on": "2026-11-15",
                },
            )
        ).status_code == 400

        # Non-positive amount, invalid IDs, boolean StrictInt, and both merchant fields -> 422
        for bad_payload in [
            {
                "profile_card_id": maya_cid,
                "amount_cents": 0,
                "category_code": "dining",
                "occurred_on": "2026-11-15",
            },
            {
                "profile_card_id": True,
                "amount_cents": 1000,
                "category_code": "dining",
                "occurred_on": "2026-11-15",
            },
            {
                "profile_card_id": maya_cid,
                "amount_cents": 1000,
                "category_code": "dining",
                "merchant_id": merchant_id,
                "merchant_text": "Harbor Bistro",
                "occurred_on": "2026-11-15",
            },
        ]:
            res = await async_client.post("/api/v1/profiles/maya/transactions", json=bad_payload)
            assert res.status_code == 422
            assert res.headers["content-type"].startswith("application/problem+json")

        # Sensitive 13-19 digit sequences in merchant_text and note -> 422, no echo, nothing stored
        session_factory = get_session_maker()
        async with session_factory() as session:
            tx_before = await session.scalar(select(func.count(Transaction.id)))
            calc_before = await session.scalar(select(func.count(TransactionRewardCalc.id)))

        for field_name, secret_val in [
            ("merchant_text", "Shop 4111 1111 1111 1111"),
            ("note", "Card 4111-1111-1111-1111 used"),
        ]:
            res = await async_client.post(
                "/api/v1/profiles/maya/transactions",
                json={
                    "profile_card_id": maya_cid,
                    "amount_cents": 1000,
                    "category_code": "dining",
                    "occurred_on": "2026-11-15",
                    field_name: secret_val,
                },
            )
            assert res.status_code == 422
            assert res.headers["content-type"].startswith("application/problem+json")
            assert secret_val not in res.text

        async with session_factory() as session:
            tx_after = await session.scalar(select(func.count(Transaction.id)))
            calc_after = await session.scalar(select(func.count(TransactionRewardCalc.id)))
            assert tx_after == tx_before
            assert calc_after == calc_before

        # 12-digit and 20-digit boundaries (including separated) are allowed; duplicates allowed
        ok1 = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": maya_cid,
                "amount_cents": 1200,
                "category_code": "dining",
                "merchant_text": "Ref 1234 5678 9012",
                "occurred_on": "2026-11-15",
                "note": "Track 1234 5678 9012 3456 7890",
            },
        )
        ok2 = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": maya_cid,
                "amount_cents": 1200,
                "category_code": "dining",
                "merchant_text": "Ref 1234 5678 9012",
                "occurred_on": "2026-11-15",
                "note": "Track 1234 5678 9012 3456 7890",
            },
        )
        assert ok1.status_code == 201
        assert ok2.status_code == 201
        assert ok1.json()["id"] != ok2.json()["id"]
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
        await async_client.post("/api/v1/profiles/dev/reset")
