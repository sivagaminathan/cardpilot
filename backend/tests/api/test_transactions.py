"""PostgreSQL integration tests for T31 transaction endpoints & immutable snapshots."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.db import close_engine, get_session_maker
from app.engine import ENGINE_VERSION
from app.models import (
    CalcRuleReference,
    Category,
    EarningRule,
    RuleSource,
    Transaction,
    TransactionRewardCalc,
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


@pytest.mark.asyncio
async def test_history_preservation_when_rule_v2_loaded_ac8(
    async_client: AsyncClient,
) -> None:
    """AC-8 / T32: loading rule v2 leaves v1 snapshot unchanged and new calc uses v2."""
    await _ensure_seeded()
    await async_client.post("/api/v1/profiles/maya/reset")

    rule_key = f"t32.travel.{uuid4().hex[:8]}"
    rule_v1_id: int | None = None
    rule_v2_id: int | None = None
    session_factory = get_session_maker()

    try:
        cards = (await async_client.get("/api/v1/profiles/maya/cards")).json()
        target_card = next(
            c for c in cards if c["card_product"]["name"] == "Northwind Cash Everyday"
        )
        card_id = target_card["id"]
        card_product_id = target_card["card_product"]["id"]
        reward_currency_id = target_card["card_product"]["reward_currency"]["id"]

        async with session_factory() as session, session.begin():
            travel_cat = await session.scalar(select(Category).where(Category.code == "travel"))
            source = await session.scalar(select(RuleSource).order_by(RuleSource.id))
            assert travel_cat is not None
            assert source is not None

            rule_v1 = EarningRule(
                rule_key=rule_key,
                version=1,
                card_product_id=card_product_id,
                reward_currency_id=reward_currency_id,
                scope_type="category",
                category_id=travel_cat.id,
                multiplier=Decimal("3.0000"),
                priority=100,
                post_cap_behavior="fallback_to_base",
                rounding="floor_units",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 6, 30),
                source_id=source.id,
                last_reviewed_on=date(2026, 1, 15),
            )
            session.add(rule_v1)
            await session.flush()
            rule_v1_id = rule_v1.id
            travel_cat_id = travel_cat.id
            source_id = source.id

        assert rule_v1_id is not None

        # 1. Submit transaction inside v1 effective range (2026-01-01..2026-06-30)
        tx1_res = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": card_id,
                "amount_cents": 10000,
                "category_code": "travel",
                "occurred_on": "2026-05-15",
                "note": "T32 v1 travel purchase",
            },
        )
        assert tx1_res.status_code == 201
        tx1_body = tx1_res.json()
        tx1_id = tx1_body["id"]
        tx1_calc_before = tx1_body["reward_calc"]

        assert Decimal(tx1_calc_before["reward_units"]) == Decimal("300.0000")
        assert tx1_calc_before["estimated_value_cents"] == 300
        assert tx1_calc_before["trace"]["applied_portions"][0]["rule_id"] == rule_v1_id
        assert tx1_calc_before["trace"]["applied_portions"][0]["rule_version"] == 1
        assert rule_v1_id in tx1_calc_before["applied_rule_ids"]

        # Capture exact DB snapshot row and CalcRuleReference rows before v2 is loaded
        async with session_factory() as session:
            db_calc_before = await session.scalar(
                select(TransactionRewardCalc).where(TransactionRewardCalc.transaction_id == tx1_id)
            )
            db_refs_before = sorted(
                (
                    await session.scalars(
                        select(CalcRuleReference.rule_id).where(
                            CalcRuleReference.calc_id == tx1_calc_before["id"]
                        )
                    )
                ).all()
            )
            assert db_calc_before is not None
            db_calc_snapshot_before = (
                db_calc_before.id,
                db_calc_before.engine_version,
                db_calc_before.reward_currency_id,
                db_calc_before.reward_units,
                db_calc_before.valuation_cents_per_unit_used,
                db_calc_before.estimated_value_cents,
                db_calc_before.trace,
                db_calc_before.created_at,
            )

        # 2. Load rule v2 for the same rule_key with non-overlapping effective range
        async with session_factory() as session, session.begin():
            rule_v2 = EarningRule(
                rule_key=rule_key,
                version=2,
                card_product_id=card_product_id,
                reward_currency_id=reward_currency_id,
                scope_type="category",
                category_id=travel_cat_id,
                multiplier=Decimal("5.0000"),
                priority=100,
                post_cap_behavior="fallback_to_base",
                rounding="floor_units",
                effective_from=date(2026, 7, 1),
                effective_to=None,
                source_id=source_id,
                last_reviewed_on=date(2026, 7, 1),
                supersedes_id=rule_v1_id,
            )
            session.add(rule_v2)
            await session.flush()
            rule_v2_id = rule_v2.id

        assert rule_v2_id is not None

        # 3. Submit new transaction inside v2 effective range (2026-07-01..)
        tx2_res = await async_client.post(
            "/api/v1/profiles/maya/transactions",
            json={
                "profile_card_id": card_id,
                "amount_cents": 10000,
                "category_code": "travel",
                "occurred_on": "2026-08-15",
                "note": "T32 v2 travel purchase",
            },
        )
        assert tx2_res.status_code == 201
        tx2_body = tx2_res.json()
        tx2_calc = tx2_body["reward_calc"]

        assert Decimal(tx2_calc["reward_units"]) == Decimal("500.0000")
        assert tx2_calc["estimated_value_cents"] == 500
        assert tx2_calc["trace"]["applied_portions"][0]["rule_id"] == rule_v2_id
        assert tx2_calc["trace"]["applied_portions"][0]["rule_version"] == 2
        assert rule_v2_id in tx2_calc["applied_rule_ids"]
        assert rule_v1_id not in tx2_calc["applied_rule_ids"]

        # Verify recommendation on v2 date also uses rule v2
        rec_res = await async_client.post(
            "/api/v1/profiles/maya/recommendations",
            json={
                "amount_cents": 10000,
                "category_code": "travel",
                "purchase_date": "2026-08-15",
                "card_ids": [card_id],
            },
        )
        assert rec_res.status_code == 200
        rec_item = rec_res.json()["ranked"][0]
        assert Decimal(rec_item["reward_units"]) == Decimal("500")
        assert rec_item["applied"][0]["rule_id"] == rule_v2_id
        assert rec_item["applied"][0]["rule_version"] == 2

        # 4. Assert both transactions retrievable via GET and tx1 snapshot is 100% unchanged
        listed = (await async_client.get("/api/v1/profiles/maya/transactions")).json()
        assert [item["id"] for item in listed] == [tx2_body["id"], tx1_id]
        listed_tx1 = next(item for item in listed if item["id"] == tx1_id)
        assert listed_tx1["reward_calc"] == tx1_calc_before

        async with session_factory() as session:
            db_calc_after = await session.scalar(
                select(TransactionRewardCalc).where(TransactionRewardCalc.transaction_id == tx1_id)
            )
            db_refs_after = sorted(
                (
                    await session.scalars(
                        select(CalcRuleReference.rule_id).where(
                            CalcRuleReference.calc_id == tx1_calc_before["id"]
                        )
                    )
                ).all()
            )
            db_tx2_refs = sorted(
                (
                    await session.scalars(
                        select(CalcRuleReference.rule_id).where(
                            CalcRuleReference.calc_id == tx2_calc["id"]
                        )
                    )
                ).all()
            )
            assert db_calc_after is not None
            assert (
                db_calc_after.id,
                db_calc_after.engine_version,
                db_calc_after.reward_currency_id,
                db_calc_after.reward_units,
                db_calc_after.valuation_cents_per_unit_used,
                db_calc_after.estimated_value_cents,
                db_calc_after.trace,
                db_calc_after.created_at,
            ) == db_calc_snapshot_before
            assert db_refs_after == db_refs_before
            assert rule_v1_id in db_refs_after
            assert rule_v2_id not in db_refs_after
            assert rule_v2_id in db_tx2_refs
    finally:
        await async_client.post("/api/v1/profiles/maya/reset")
        if rule_v2_id is not None or rule_v1_id is not None:
            async with session_factory() as session, session.begin():
                if rule_v2_id is not None:
                    await session.execute(delete(EarningRule).where(EarningRule.id == rule_v2_id))
                if rule_v1_id is not None:
                    await session.execute(delete(EarningRule).where(EarningRule.id == rule_v1_id))
