"""Database ORM and migration tests for reference tables (T21).

Runs against real PostgreSQL (no SQLite substitution) to verify:
- Base.metadata table definitions and columns
- Unique constraints
- Foreign-key behaviors (RESTRICT and SET NULL)
- CHECK constraints
- Nullable merchants.default_category_id
- Independent default [] and PostgreSQL ARRAY persistence for merchants.tags
- Alembic downgrade and upgrade round-trip
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from app.config import get_settings
from app.db import Base
from app.models import (
    CardProduct,
    Category,
    Merchant,
    RewardCurrency,
    RuleSource,
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


def test_metadata_contains_exact_five_reference_tables() -> None:
    expected = {
        "reward_currencies",
        "categories",
        "merchants",
        "card_products",
        "rule_sources",
    }
    assert set(Base.metadata.tables.keys()) == expected


def test_alembic_downgrade_and_upgrade_roundtrip() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # Downgrade T21 migration -> empty initial migration, then upgrade back to head
    command.downgrade(alembic_cfg, "f5f1d05a3578")
    command.upgrade(alembic_cfg, "head")

    # Verify all five tables exist in PostgreSQL after upgrade
    import asyncio

    async def _get_tables() -> set[str]:
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(
                    lambda sync_conn: set(inspect(sync_conn).get_table_names())
                )
        finally:
            await engine.dispose()

    tables = asyncio.run(_get_tables())
    assert {
        "reward_currencies",
        "categories",
        "merchants",
        "card_products",
        "rule_sources",
    }.issubset(tables)


@pytest.mark.asyncio
async def test_merchant_tags_default_not_shared_and_nullable_category(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    m1 = Merchant(name=f"Cafe A {suffix}")
    m2 = Merchant(name=f"Cafe B {suffix}")
    m_tagged = Merchant(
        name=f"Bulk Club {suffix}",
        default_category_id=None,
        tags=["warehouse_club", "wholesale"],
    )
    db_session.add_all([m1, m2, m_tagged])
    await db_session.flush()

    assert m1.tags == []
    assert m2.tags == []
    assert m1.tags is not m2.tags

    loaded = await db_session.scalar(select(Merchant).where(Merchant.id == m_tagged.id))
    assert loaded is not None
    assert loaded.default_category_id is None
    assert loaded.tags == ["warehouse_club", "wholesale"]


@pytest.mark.asyncio
async def test_foreign_key_set_null_and_restrict_behaviors(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    cat = Category(code=f"dining_{suffix}", name="Dining")
    curr = RewardCurrency(
        code=f"PTS_{suffix}",
        name="Northstar Points",
        kind="points",
        is_cash_equivalent=False,
        default_cents_per_unit=Decimal("1.2500"),
    )
    db_session.add_all([cat, curr])
    await db_session.flush()

    merchant = Merchant(name=f"Acme Bistro {suffix}", default_category_id=cat.id)
    product = CardProduct(
        issuer_name="Northwind Bank",
        name=f"Sapphire Demo {suffix}",
        reward_currency_id=curr.id,
        annual_fee_cents=9500,
        network_label="DemoNet",
        description="Fictional travel card",
    )
    db_session.add_all([merchant, product])
    await db_session.flush()

    # Deleting category sets merchant.default_category_id to NULL (ON DELETE SET NULL)
    merchant_id = merchant.id
    await db_session.delete(cat)
    await db_session.flush()
    db_session.expire(merchant)
    reloaded_merchant = await db_session.scalar(select(Merchant).where(Merchant.id == merchant_id))
    assert reloaded_merchant is not None
    assert reloaded_merchant.default_category_id is None

    # Deleting reward_currency referenced by card_product raises IntegrityError (RESTRICT)
    async with db_session.begin_nested():
        await db_session.delete(curr)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_unique_constraints(db_session: AsyncSession) -> None:
    suffix = uuid4().hex[:8]
    c1 = RewardCurrency(
        code=f"USD_{suffix}",
        name="Cash",
        kind="cash_back",
        is_cash_equivalent=True,
        default_cents_per_unit=Decimal("1.0000"),
    )
    cat1 = Category(code=f"cat_{suffix}", name="Cat")
    m1 = Merchant(name=f"Merch_{suffix}")
    s1 = RuleSource(
        title=f"Source_{suffix}",
        kind="fictional_sample",
        url=None,
        notes="Sample",
        last_reviewed_on=date(2026, 11, 15),
    )
    db_session.add_all([c1, cat1, m1, s1])
    await db_session.flush()

    p1 = CardProduct(
        issuer_name="IssuerX",
        name=f"Card_{suffix}",
        reward_currency_id=c1.id,
        annual_fee_cents=0,
        network_label="DemoNet",
    )
    db_session.add(p1)
    await db_session.flush()

    # Duplicate currency code
    async with db_session.begin_nested():
        db_session.add(
            RewardCurrency(
                code=f"USD_{suffix}",
                name="Other",
                kind="cash_back",
                default_cents_per_unit=Decimal("1.0000"),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Duplicate category code
    async with db_session.begin_nested():
        db_session.add(Category(code=f"cat_{suffix}", name="Other Cat"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Duplicate merchant name
    async with db_session.begin_nested():
        db_session.add(Merchant(name=f"Merch_{suffix}"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Duplicate (issuer_name, name) on card_products
    async with db_session.begin_nested():
        db_session.add(
            CardProduct(
                issuer_name="IssuerX",
                name=f"Card_{suffix}",
                reward_currency_id=c1.id,
                annual_fee_cents=0,
                network_label="DemoNet",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Duplicate rule_sources.title
    async with db_session.begin_nested():
        db_session.add(
            RuleSource(
                title=f"Source_{suffix}",
                kind="public_doc_example",
                last_reviewed_on=date(2026, 11, 15),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_check_constraints(db_session: AsyncSession) -> None:
    suffix = uuid4().hex[:8]
    curr = RewardCurrency(
        code=f"CHK_{suffix}",
        name="Check Curr",
        kind="points",
        default_cents_per_unit=Decimal("1.0000"),
    )
    db_session.add(curr)
    await db_session.flush()

    # Invalid reward_currencies.kind
    async with db_session.begin_nested():
        db_session.add(
            RewardCurrency(
                code=f"BAD_KIND_{suffix}",
                name="Bad",
                kind="crypto",
                default_cents_per_unit=Decimal("1.0000"),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Non-positive default_cents_per_unit
    async with db_session.begin_nested():
        db_session.add(
            RewardCurrency(
                code=f"BAD_VAL_{suffix}",
                name="Bad",
                kind="points",
                default_cents_per_unit=Decimal("0"),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Negative annual_fee_cents
    async with db_session.begin_nested():
        db_session.add(
            CardProduct(
                issuer_name="IssuerY",
                name=f"BadFee_{suffix}",
                reward_currency_id=curr.id,
                annual_fee_cents=-100,
                network_label="DemoNet",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Invalid rule_sources.kind
    async with db_session.begin_nested():
        db_session.add(
            RuleSource(
                title=f"BadSource_{suffix}",
                kind="real_bank_scrape",
                last_reviewed_on=date(2026, 11, 15),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()
