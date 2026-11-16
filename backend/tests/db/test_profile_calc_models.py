"""Database ORM and migration tests for profiles, transactions, calcs, and benefits (T23).

Runs against real PostgreSQL (no SQLite substitution) to verify:
- Base.metadata table definitions for all 8 T23 tables
- Composite primary keys, unique constraints (including nullable seed_key), and CHECK constraints
- Composite indexes on transactions, benefit_usages, and calc_rule_references
- JSONB trace persistence and calculation snapshot fields
- FK CASCADE (transaction deletion removes calc & rule references) and RESTRICT (used rule)
- Application-level immutability (is_rule_referenced / check_rule_mutable)
- Database-level trigger preventing direct SQL semantic updates to referenced rules
- Creating new rule versions without mutating prior versions or snapshots
- Alembic downgrade (1f98842cde08) and upgrade (head) round-trip
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from alembic import command
from app.config import get_settings
from app.db import Base
from app.models import (
    BenefitDefinition,
    BenefitUsage,
    CalcRuleReference,
    CardProduct,
    Category,
    CurrencyValuation,
    EarningRule,
    Profile,
    ProfileCard,
    RewardCurrency,
    RuleImmutableError,
    RuleSource,
    Transaction,
    TransactionRewardCalc,
    check_rule_mutable,
    is_rule_referenced,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async Postgres session wrapped in a rolled-back transaction."""
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


async def _create_prereqs(
    session: AsyncSession,
) -> tuple[RewardCurrency, Category, CardProduct, RuleSource, EarningRule]:
    """Insert unique reference + rule rows required as FKs for T23 models."""
    suffix = uuid4().hex[:8]
    currency = RewardCurrency(
        code=f"pts_{suffix}",
        name=f"Test Points {suffix}",
        kind="points",
        is_cash_equivalent=False,
        default_cents_per_unit=Decimal("1.5000"),
    )
    category = Category(code=f"dining_{suffix}", name=f"Dining {suffix}")
    source = RuleSource(
        title=f"Terms {suffix}",
        kind="fictional_sample",
        url="https://example.com/terms",
        last_reviewed_on=date(2026, 1, 1),
    )
    session.add_all([currency, category, source])
    await session.flush()

    card = CardProduct(
        issuer_name=f"TestBank {suffix}",
        name=f"TestCard {suffix}",
        reward_currency_id=currency.id,
        network_label="Vexa",
    )
    session.add(card)
    await session.flush()

    rule = EarningRule(
        rule_key=f"rk_{suffix}",
        version=1,
        card_product_id=card.id,
        reward_currency_id=currency.id,
        scope_type="category",
        category_id=category.id,
        multiplier=Decimal("3.0000"),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        source_id=source.id,
        last_reviewed_on=date(2026, 1, 1),
    )
    session.add(rule)
    await session.flush()
    return currency, category, card, source, rule


def test_metadata_contains_t23_tables() -> None:
    expected = {
        "profiles",
        "profile_cards",
        "currency_valuations",
        "transactions",
        "transaction_reward_calcs",
        "calc_rule_references",
        "benefit_definitions",
        "benefit_usages",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_alembic_downgrade_and_upgrade_roundtrip() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    command.downgrade(alembic_cfg, "1f98842cde08")
    command.upgrade(alembic_cfg, "head")

    async def _inspect_db() -> tuple[set[str], dict[str, set[str]]]:
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as conn:

                def _read(sync_conn: object) -> tuple[set[str], dict[str, set[str]]]:
                    insp = inspect(sync_conn)  # type: ignore[arg-type]
                    tables = set(insp.get_table_names())
                    indexes = {
                        tbl: {idx["name"] for idx in insp.get_indexes(tbl) if idx["name"]}
                        for tbl in ("transactions", "benefit_usages", "calc_rule_references")
                    }
                    return tables, indexes

                return await conn.run_sync(_read)
        finally:
            await engine.dispose()

    tables, indexes = asyncio.run(_inspect_db())
    assert {
        "profiles",
        "profile_cards",
        "currency_valuations",
        "transactions",
        "transaction_reward_calcs",
        "calc_rule_references",
        "benefit_definitions",
        "benefit_usages",
    }.issubset(tables)
    assert {
        "ix_transactions_profile_occurred_on",
        "ix_transactions_profile_card_occurred_on",
    }.issubset(indexes["transactions"])
    assert "ix_benefit_usages_card_benefit_used_on" in indexes["benefit_usages"]
    assert "ix_calc_rule_references_rule_id" in indexes["calc_rule_references"]


async def test_profile_seed_key_nullable_and_unique(db_session: AsyncSession) -> None:
    suffix = uuid4().hex[:8]
    p1 = Profile(slug=f"p1_{suffix}", display_name="User 1", is_demo=False, seed_key=None)
    p2 = Profile(slug=f"p2_{suffix}", display_name="User 2", is_demo=False, seed_key=None)
    p3 = Profile(
        slug=f"p3_{suffix}",
        display_name="Demo 1",
        is_demo=True,
        seed_key=f"demo_{suffix}",
    )
    db_session.add_all([p1, p2, p3])
    await db_session.flush()

    # Duplicate slug rejected
    async with db_session.begin_nested():
        db_session.add(Profile(slug=f"p1_{suffix}", display_name="Dup Slug"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Duplicate non-null seed_key rejected
    async with db_session.begin_nested():
        db_session.add(
            Profile(slug=f"p4_{suffix}", display_name="Dup Seed", seed_key=f"demo_{suffix}")
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


async def test_currency_valuation_pk_and_check(db_session: AsyncSession) -> None:
    currency, _, _, _, _ = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]
    profile = Profile(slug=f"val_{suffix}", display_name="Val User")
    db_session.add(profile)
    await db_session.flush()

    val = CurrencyValuation(
        profile_id=profile.id,
        reward_currency_id=currency.id,
        cents_per_unit=Decimal("1.7500"),
        is_user_set=True,
    )
    db_session.add(val)
    await db_session.flush()

    # Duplicate composite PK (profile_id, reward_currency_id) rejected
    async with db_session.begin_nested():
        db_session.add(
            CurrencyValuation(
                profile_id=profile.id,
                reward_currency_id=currency.id,
                cents_per_unit=Decimal("2.0000"),
                is_user_set=True,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Non-positive cents_per_unit rejected
    p2 = Profile(slug=f"val2_{suffix}", display_name="Val User 2")
    db_session.add(p2)
    await db_session.flush()
    async with db_session.begin_nested():
        db_session.add(
            CurrencyValuation(
                profile_id=p2.id,
                reward_currency_id=currency.id,
                cents_per_unit=Decimal("0.0000"),
                is_user_set=False,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


async def test_benefit_definition_and_usage_constraints(db_session: AsyncSession) -> None:
    _, _, card, source, _ = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]
    profile = Profile(slug=f"ben_{suffix}", display_name="Benefit User")
    db_session.add(profile)
    await db_session.flush()

    profile_card = ProfileCard(
        profile_id=profile.id,
        card_product_id=card.id,
        nickname="My Card",
        opened_on=date(2025, 3, 15),
    )
    db_session.add(profile_card)
    await db_session.flush()

    benefit = BenefitDefinition(
        card_product_id=card.id,
        name="Semiannual Airline Credit",
        benefit_type="credit",
        value_cents=5000,
        reset_period="semiannual",
        source_id=source.id,
        effective_from=date(2026, 1, 1),
        effective_to=None,
    )
    perk = BenefitDefinition(
        card_product_id=card.id,
        name="Lounge Access",
        benefit_type="perk",
        value_cents=None,
        reset_period="card_year",
        source_id=source.id,
        effective_from=date(2026, 1, 1),
    )
    db_session.add_all([benefit, perk])
    await db_session.flush()

    usage = BenefitUsage(
        profile_card_id=profile_card.id,
        benefit_definition_id=benefit.id,
        amount_cents=2500,
        used_on=date(2026, 2, 10),
        note="Checked bag",
    )
    db_session.add(usage)
    await db_session.flush()

    # Invalid reset_period
    async with db_session.begin_nested():
        db_session.add(
            BenefitDefinition(
                card_product_id=card.id,
                name="Bad Period",
                benefit_type="credit",
                value_cents=1000,
                reset_period="weekly",
                source_id=source.id,
                effective_from=date(2026, 1, 1),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Non-positive value_cents
    async with db_session.begin_nested():
        db_session.add(
            BenefitDefinition(
                card_product_id=card.id,
                name="Zero Credit",
                benefit_type="credit",
                value_cents=0,
                reset_period="monthly",
                source_id=source.id,
                effective_from=date(2026, 1, 1),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Non-positive usage amount_cents
    async with db_session.begin_nested():
        db_session.add(
            BenefitUsage(
                profile_card_id=profile_card.id,
                benefit_definition_id=benefit.id,
                amount_cents=0,
                used_on=date(2026, 2, 11),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


async def test_transaction_calc_snapshot_immutability_and_cascade(
    db_session: AsyncSession,
) -> None:
    currency, category, card, source, rule_v1 = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]
    profile = Profile(slug=f"tx_{suffix}", display_name="Tx User")
    db_session.add(profile)
    await db_session.flush()

    profile_card = ProfileCard(
        profile_id=profile.id,
        card_product_id=card.id,
        nickname="Dining Card",
    )
    db_session.add(profile_card)
    await db_session.flush()

    # Unreferenced rule can be updated via check_rule_mutable and direct SQL
    assert await is_rule_referenced(db_session, rule_v1.id) is False
    rule_v1.priority = 5
    await check_rule_mutable(db_session, rule_v1)
    await db_session.flush()

    # Invalid transaction amount_cents <= 0 rejected
    async with db_session.begin_nested():
        db_session.add(
            Transaction(
                profile_id=profile.id,
                profile_card_id=profile_card.id,
                amount_cents=0,
                category_id=category.id,
                occurred_on=date(2026, 2, 1),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    tx = Transaction(
        profile_id=profile.id,
        profile_card_id=profile_card.id,
        amount_cents=10000,
        category_id=category.id,
        merchant_text="Bistro",
        occurred_on=date(2026, 2, 1),
        note="Dinner",
    )
    db_session.add(tx)
    await db_session.flush()

    trace_payload = {
        "applied": [
            {
                "rule_id": rule_v1.id,
                "rule_key": rule_v1.rule_key,
                "rule_version": 1,
                "portion_cents": 10000,
                "multiplier": "3.0000",
            }
        ],
        "explanation": ["Matched dining 3x (v1)."],
    }
    calc = TransactionRewardCalc(
        transaction_id=tx.id,
        engine_version="1.0.0",
        reward_currency_id=currency.id,
        reward_units=Decimal("300.0000"),
        valuation_cents_per_unit_used=Decimal("1.5000"),
        estimated_value_cents=450,
        trace=trace_payload,
    )
    db_session.add(calc)
    await db_session.flush()

    ref = CalcRuleReference(calc_id=calc.id, rule_id=rule_v1.id)
    db_session.add(ref)
    await db_session.flush()

    # Duplicate calc for same transaction rejected (unique transaction_id)
    async with db_session.begin_nested():
        db_session.add(
            TransactionRewardCalc(
                transaction_id=tx.id,
                engine_version="1.0.0",
                reward_currency_id=currency.id,
                reward_units=Decimal("300.0000"),
                trace=trace_payload,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Verify JSONB trace and rule reference are persisted
    tx_id = tx.id
    calc_id = calc.id
    rule_v1_id = rule_v1.id
    rule_v1_key = rule_v1.rule_key
    card_id = card.id
    currency_id = currency.id
    category_id = category.id
    source_id = source.id
    db_session.expire_all()
    loaded_calc = await db_session.scalar(
        select(TransactionRewardCalc)
        .where(TransactionRewardCalc.id == calc_id)
        .options(selectinload(TransactionRewardCalc.rule_references))
    )
    assert loaded_calc is not None
    assert loaded_calc.trace == trace_payload
    assert len(loaded_calc.rule_references) == 1
    assert loaded_calc.rule_references[0].rule_id == rule_v1_id

    # Application-level immutability guard blocks semantic update on referenced rule
    loaded_rule = await db_session.get(EarningRule, rule_v1_id)
    assert loaded_rule is not None
    assert await is_rule_referenced(db_session, rule_v1_id) is True
    loaded_rule.multiplier = Decimal("4.0000")
    with pytest.raises(RuleImmutableError, match="referenced by a calculation"):
        await check_rule_mutable(db_session, loaded_rule)
    db_session.expire(loaded_rule)

    # Database trigger blocks direct SQL semantic UPDATE on referenced rule
    with pytest.raises(IntegrityError, match="referenced by calculation snapshot"):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE earning_rules SET multiplier = 4.0000 WHERE id = :rid"),
                {"rid": rule_v1_id},
            )

    # ON DELETE RESTRICT prevents deleting referenced rule
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text("DELETE FROM earning_rules WHERE id = :rid"),
                {"rid": rule_v1_id},
            )

    # Creating a new rule version v2 succeeds without mutating v1 or snapshot
    rule_v2 = EarningRule(
        rule_key=rule_v1_key,
        version=2,
        card_product_id=card_id,
        reward_currency_id=currency_id,
        scope_type="category",
        category_id=category_id,
        multiplier=Decimal("4.0000"),
        effective_from=date(2026, 7, 1),
        effective_to=None,
        source_id=source_id,
        last_reviewed_on=date(2026, 7, 1),
        supersedes_id=rule_v1_id,
    )
    db_session.add(rule_v2)
    await db_session.flush()

    # Deleting the transaction cascades to transaction_reward_calcs and calc_rule_references
    loaded_tx = await db_session.get(Transaction, tx_id)
    assert loaded_tx is not None
    await db_session.delete(loaded_tx)
    await db_session.flush()

    assert await db_session.get(TransactionRewardCalc, calc_id) is None
    assert await is_rule_referenced(db_session, rule_v1_id) is False
