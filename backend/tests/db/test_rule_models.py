"""Database ORM and migration tests for rules, exclusions, and caps (T22).

Runs against real PostgreSQL (no SQLite substitution) to verify:
- Base.metadata table definitions and columns for spend_caps, earning_rules, rule_exclusions
- ORM relationships (cap, exclusions, supersedes, source)
- Unique constraints on spend_caps(card_product_id, cap_group_key) and
  earning_rules(rule_key, version)
- CHECK constraints for periods, amounts, versions, scopes, multipliers,
  thresholds, dates, and exclusions
- PostgreSQL btree_gist daterange exclusion constraint preventing overlapping
  effective dates per rule_key
- Immutability enforcement boundary (ensure_rule_mutable / RuleImmutableError)
- Alembic downgrade (0e8ce330266b) and upgrade (head) round-trip
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
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from alembic import command
from app.config import get_settings
from app.db import Base
from app.models import (
    CardProduct,
    Category,
    EarningRule,
    Merchant,
    RewardCurrency,
    RuleExclusion,
    RuleImmutableError,
    RuleSource,
    SpendCap,
    ensure_rule_mutable,
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
) -> tuple[RewardCurrency, Category, Merchant, CardProduct, RuleSource]:
    """Insert unique reference rows required as FKs for T22 models."""
    suffix = uuid4().hex[:8]
    currency = RewardCurrency(
        code=f"pts_{suffix}",
        name=f"Test Points {suffix}",
        kind="points",
        is_cash_equivalent=False,
        default_cents_per_unit=Decimal("1.5000"),
    )
    category = Category(code=f"dining_{suffix}", name=f"Dining {suffix}")
    session.add_all([currency, category])
    await session.flush()

    merchant = Merchant(
        name=f"Bistro {suffix}",
        default_category_id=category.id,
        tags=["restaurant"],
    )
    card = CardProduct(
        issuer_name=f"TestBank {suffix}",
        name=f"TestCard {suffix}",
        reward_currency_id=currency.id,
        network_label="Vexa",
    )
    source = RuleSource(
        title=f"Terms {suffix}",
        kind="fictional_sample",
        url="https://example.com/terms",
        last_reviewed_on=date(2026, 1, 1),
    )
    session.add_all([merchant, card, source])
    await session.flush()
    return currency, category, merchant, card, source


def test_metadata_contains_rule_tables() -> None:
    expected = {"spend_caps", "earning_rules", "rule_exclusions"}
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_alembic_downgrade_and_upgrade_roundtrip() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    command.downgrade(alembic_cfg, "0e8ce330266b")
    command.upgrade(alembic_cfg, "head")

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
    assert {"spend_caps", "earning_rules", "rule_exclusions"}.issubset(tables)


async def test_spend_cap_and_earning_rule_relationships(db_session: AsyncSession) -> None:
    currency, category, _, card, source = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]

    cap = SpendCap(
        cap_group_key=f"dining_qtr_{suffix}",
        card_product_id=card.id,
        cap_amount_cents=150000,
        period="quarterly",
    )
    db_session.add(cap)
    await db_session.flush()

    rule_v1 = EarningRule(
        rule_key=f"rule_{suffix}",
        version=1,
        card_product_id=card.id,
        reward_currency_id=currency.id,
        scope_type="category",
        category_id=category.id,
        multiplier=Decimal("3.0000"),
        cap_id=cap.id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        source_id=source.id,
        last_reviewed_on=date(2026, 1, 15),
    )
    db_session.add(rule_v1)
    await db_session.flush()

    rule_v2 = EarningRule(
        rule_key=f"rule_{suffix}",
        version=2,
        card_product_id=card.id,
        reward_currency_id=currency.id,
        scope_type="category",
        category_id=category.id,
        multiplier=Decimal("4.0000"),
        cap_id=cap.id,
        effective_from=date(2026, 7, 1),
        effective_to=None,
        source_id=source.id,
        last_reviewed_on=date(2026, 7, 1),
        supersedes_id=rule_v1.id,
    )
    db_session.add(rule_v2)
    await db_session.flush()

    exclusion = RuleExclusion(
        rule_id=rule_v2.id,
        exclusion_type="merchant_tag",
        target_tag="wholesale",
        reason="Wholesale clubs excluded",
    )
    db_session.add(exclusion)
    await db_session.flush()
    rule_v2_id = rule_v2.id
    db_session.expire_all()

    loaded = await db_session.scalar(
        select(EarningRule)
        .where(EarningRule.id == rule_v2_id)
        .options(
            selectinload(EarningRule.cap),
            selectinload(EarningRule.exclusions),
            selectinload(EarningRule.supersedes),
            selectinload(EarningRule.source),
        )
    )
    assert loaded is not None
    assert loaded.cap is not None
    assert loaded.cap.cap_amount_cents == 150000
    assert len(loaded.exclusions) == 1
    assert loaded.exclusions[0].target_tag == "wholesale"
    assert loaded.supersedes is not None
    assert loaded.supersedes.id == rule_v1.id
    assert loaded.source.id == source.id


async def test_spend_cap_unique_and_checks(db_session: AsyncSession) -> None:
    _, _, _, card, _ = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]

    db_session.add(
        SpendCap(
            cap_group_key=f"cap_{suffix}",
            card_product_id=card.id,
            cap_amount_cents=50000,
            period="monthly",
        )
    )
    await db_session.flush()

    async with db_session.begin_nested():
        db_session.add(
            SpendCap(
                cap_group_key=f"cap_{suffix}",
                card_product_id=card.id,
                cap_amount_cents=60000,
                period="monthly",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async with db_session.begin_nested():
        db_session.add(
            SpendCap(
                cap_group_key=f"cap_bad_period_{suffix}",
                card_product_id=card.id,
                cap_amount_cents=50000,
                period="weekly",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async with db_session.begin_nested():
        db_session.add(
            SpendCap(
                cap_group_key=f"cap_zero_{suffix}",
                card_product_id=card.id,
                cap_amount_cents=0,
                period="monthly",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


async def test_earning_rule_unique_and_check_constraints(db_session: AsyncSession) -> None:
    currency, category, merchant, card, source = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]

    base_kwargs = {
        "card_product_id": card.id,
        "reward_currency_id": currency.id,
        "multiplier": Decimal("2.0000"),
        "effective_from": date(2026, 1, 1),
        "source_id": source.id,
        "last_reviewed_on": date(2026, 1, 1),
    }

    # Unique (rule_key, version)
    db_session.add(
        EarningRule(
            rule_key=f"rk_{suffix}",
            version=1,
            scope_type="base",
            **base_kwargs,
        )
    )
    await db_session.flush()

    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_{suffix}",
                version=1,
                scope_type="base",
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Invalid version < 1
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_ver_{suffix}",
                version=0,
                scope_type="base",
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Scope target mismatches: category without category_id, base/merchant with category_id
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_cat_missing_{suffix}",
                version=1,
                scope_type="category",
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_base_extra_{suffix}",
                version=1,
                scope_type="base",
                category_id=category.id,
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_merch_extra_{suffix}",
                version=1,
                scope_type="merchant",
                merchant_id=merchant.id,
                category_id=category.id,
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Negative multiplier
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_neg_mult_{suffix}",
                version=1,
                card_product_id=card.id,
                reward_currency_id=currency.id,
                scope_type="base",
                multiplier=Decimal("-1.0000"),
                effective_from=date(2026, 1, 1),
                source_id=source.id,
                last_reviewed_on=date(2026, 1, 1),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # min_transaction_cents <= 0
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_min_tx_{suffix}",
                version=1,
                scope_type="base",
                min_transaction_cents=0,
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # threshold_period without min_period_spend_cents
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_thresh_pair_{suffix}",
                version=1,
                scope_type="base",
                threshold_period="monthly",
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # effective_to < effective_from
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=f"rk_bad_dates_{suffix}",
                version=1,
                scope_type="base",
                effective_to=date(2025, 12, 31),
                **base_kwargs,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


async def test_earning_rule_non_overlapping_effective_dates(db_session: AsyncSession) -> None:
    currency, _, _, card, source = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]
    rule_key = f"rk_overlap_{suffix}"

    # Version 1: 2026-01-01 .. 2026-06-30
    db_session.add(
        EarningRule(
            rule_key=rule_key,
            version=1,
            card_product_id=card.id,
            reward_currency_id=currency.id,
            scope_type="base",
            multiplier=Decimal("1.5000"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            source_id=source.id,
            last_reviewed_on=date(2026, 1, 1),
        )
    )
    await db_session.flush()

    # Adjacent non-overlapping version 2: 2026-07-01 .. open-ended -> allowed
    db_session.add(
        EarningRule(
            rule_key=rule_key,
            version=2,
            card_product_id=card.id,
            reward_currency_id=currency.id,
            scope_type="base",
            multiplier=Decimal("2.0000"),
            effective_from=date(2026, 7, 1),
            effective_to=None,
            source_id=source.id,
            last_reviewed_on=date(2026, 7, 1),
        )
    )
    await db_session.flush()

    # Overlapping on boundary 2026-06-30 -> rejected by btree_gist exclusion constraint
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=rule_key,
                version=3,
                card_product_id=card.id,
                reward_currency_id=currency.id,
                scope_type="base",
                multiplier=Decimal("2.5000"),
                effective_from=date(2026, 6, 30),
                effective_to=date(2026, 6, 30),
                source_id=source.id,
                last_reviewed_on=date(2026, 6, 30),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Overlapping with open-ended version 2 -> rejected
    async with db_session.begin_nested():
        db_session.add(
            EarningRule(
                rule_key=rule_key,
                version=4,
                card_product_id=card.id,
                reward_currency_id=currency.id,
                scope_type="base",
                multiplier=Decimal("3.0000"),
                effective_from=date(2026, 8, 1),
                effective_to=date(2026, 9, 1),
                source_id=source.id,
                last_reviewed_on=date(2026, 8, 1),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Same overlapping dates for a DIFFERENT rule_key -> allowed
    db_session.add(
        EarningRule(
            rule_key=f"rk_other_{suffix}",
            version=1,
            card_product_id=card.id,
            reward_currency_id=currency.id,
            scope_type="base",
            multiplier=Decimal("1.0000"),
            effective_from=date(2026, 1, 1),
            effective_to=None,
            source_id=source.id,
            last_reviewed_on=date(2026, 1, 1),
        )
    )
    await db_session.flush()


async def test_rule_exclusion_target_checks(db_session: AsyncSession) -> None:
    currency, category, merchant, card, source = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]

    rule = EarningRule(
        rule_key=f"rk_excl_{suffix}",
        version=1,
        card_product_id=card.id,
        reward_currency_id=currency.id,
        scope_type="base",
        multiplier=Decimal("1.5000"),
        effective_from=date(2026, 1, 1),
        source_id=source.id,
        last_reviewed_on=date(2026, 1, 1),
    )
    db_session.add(rule)
    await db_session.flush()

    # Valid category and merchant exclusions
    db_session.add_all(
        [
            RuleExclusion(
                rule_id=rule.id,
                exclusion_type="category",
                target_category_id=category.id,
                reason="Category excluded",
            ),
            RuleExclusion(
                rule_id=rule.id,
                exclusion_type="merchant",
                target_merchant_id=merchant.id,
                reason="Merchant excluded",
            ),
        ]
    )
    await db_session.flush()

    # Mismatched target for category exclusion (missing target_category_id)
    async with db_session.begin_nested():
        db_session.add(
            RuleExclusion(
                rule_id=rule.id,
                exclusion_type="category",
                target_merchant_id=merchant.id,
                reason="Invalid target",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Blank target_tag for merchant_tag exclusion
    async with db_session.begin_nested():
        db_session.add(
            RuleExclusion(
                rule_id=rule.id,
                exclusion_type="merchant_tag",
                target_tag="   ",
                reason="Blank tag",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


async def test_ensure_rule_mutable_enforcement_boundary(db_session: AsyncSession) -> None:
    currency, _, _, card, source = await _create_prereqs(db_session)
    suffix = uuid4().hex[:8]

    rule = EarningRule(
        rule_key=f"rk_mut_{suffix}",
        version=1,
        card_product_id=card.id,
        reward_currency_id=currency.id,
        scope_type="base",
        multiplier=Decimal("1.5000"),
        effective_from=date(2026, 1, 1),
        source_id=source.id,
        last_reviewed_on=date(2026, 1, 1),
    )
    db_session.add(rule)
    await db_session.flush()

    # Unreferenced rule can be updated cleanly
    rule.multiplier = Decimal("2.0000")
    ensure_rule_mutable(rule, is_referenced_by_calc=False)
    await db_session.flush()

    # Referenced rule raises RuleImmutableError when semantic columns change
    rule.multiplier = Decimal("3.0000")
    with pytest.raises(RuleImmutableError, match="referenced by a calculation"):
        ensure_rule_mutable(rule, is_referenced_by_calc=True)
