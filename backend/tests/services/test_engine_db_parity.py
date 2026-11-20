"""PostgreSQL integration tests proving DB-assembled inputs match engine fixtures (T28)."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import close_engine, get_session_maker
from app.engine import (
    CardEvaluation,
    Purchase,
    evaluate_purchase,
    rank_card_evaluations,
)
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
    SpendCap,
    Transaction,
)
from app.services.recommendations import assemble_profile_engine_inputs

_FIXTURES_PATH = Path(__file__).resolve().parents[1] / "engine" / "fixtures" / "scenarios.json"
_SCENARIOS: list[dict[str, Any]] = json.loads(_FIXTURES_PATH.read_text(encoding="utf-8"))[
    "scenarios"
]


@pytest.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncGenerator[None, None]:
    """Dispose the shared asyncpg engine before each test's event loop closes."""
    yield
    await close_engine()


async def _get_or_create_category(session: Any, code: str, cache: dict[str, Category]) -> Category:
    if code in cache:
        return cache[code]
    existing = await session.scalar(select(Category).where(Category.code == code))
    if existing is None:
        existing = Category(code=code, name=code.replace("_", " ").title())
        session.add(existing)
        await session.flush()
    cache[code] = existing
    return existing


async def _get_or_create_merchant(
    session: Any,
    name: str,
    cache: dict[str, Merchant],
) -> Merchant:
    if name in cache:
        return cache[name]
    existing = await session.scalar(select(Merchant).where(Merchant.name == name))
    if existing is None:
        existing = Merchant(name=name, tags=[])
        session.add(existing)
        await session.flush()
    cache[name] = existing
    return existing


async def _get_or_create_currency(
    session: Any,
    code: str,
    cache: dict[str, RewardCurrency],
) -> RewardCurrency:
    if code in cache:
        return cache[code]
    existing = await session.scalar(select(RewardCurrency).where(RewardCurrency.code == code))
    if existing is None:
        existing = RewardCurrency(
            code=code,
            name=code,
            kind="points",
            is_cash_equivalent=False,
            default_cents_per_unit=Decimal("1.0000"),
        )
        session.add(existing)
        await session.flush()
    cache[code] = existing
    return existing


def _assert_db_card_matches(
    actual: CardEvaluation,
    expected: dict[str, Any],
    card_id_map: dict[int, int],
    rule_id_map: dict[int, int],
) -> None:
    assert card_id_map[actual.card_id] == expected["card_id"]
    if "reward_currency" in expected:
        assert actual.reward_currency == expected["reward_currency"]
    if "reward_units" in expected:
        assert actual.reward_units == Decimal(expected["reward_units"])
        assert str(actual.reward_units) == expected["reward_units"]
    if "estimated_value_cents" in expected:
        assert actual.estimated_value_cents == expected["estimated_value_cents"]
    if "rejection_reason" in expected:
        assert actual.rejection_reason == expected["rejection_reason"]
    if "rejection_message" in expected:
        assert actual.rejection_message == expected["rejection_message"]
    if "warnings" in expected:
        assert actual.warnings == tuple(expected["warnings"])
    if "applied_portions" in expected:
        assert len(actual.applied_portions) == len(expected["applied_portions"])
        for act_p, exp_p in zip(actual.applied_portions, expected["applied_portions"], strict=True):
            assert act_p.portion_cents == exp_p["portion_cents"]
            assert rule_id_map[act_p.rule_id] == exp_p["rule_id"]
            assert act_p.rule_version == exp_p["rule_version"]
            assert act_p.multiplier == Decimal(exp_p["multiplier"])
    if "explanation_contains" in expected:
        joined = " ".join(actual.explanation)
        for snippet in expected["explanation_contains"]:
            assert snippet in joined


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s["id"] for s in _SCENARIOS])
async def test_db_assembled_inputs_match_golden_scenario(scenario: dict[str, Any]) -> None:
    """Loading scenario rows into PostgreSQL and assembling via service matches scenarios.json."""
    await close_engine()
    session_factory = get_session_maker()
    run_tag = uuid4().hex[:8]

    raw_purchase = scenario["purchase"]
    purchase = Purchase(
        amount_cents=raw_purchase["amount_cents"],
        category=raw_purchase["category"],
        purchase_date=date.fromisoformat(raw_purchase["purchase_date"]),
        merchant=raw_purchase.get("merchant"),
        merchant_tags=tuple(raw_purchase.get("merchant_tags", ())),
    )

    async with session_factory() as session:
        try:
            cat_cache: dict[str, Category] = {}
            merch_cache: dict[str, Merchant] = {}
            curr_cache: dict[str, RewardCurrency] = {}

            purchase_cat = await _get_or_create_category(session, purchase.category, cat_cache)
            if purchase.merchant:
                await _get_or_create_merchant(session, purchase.merchant, merch_cache)

            source = RuleSource(
                title=f"Parity Source {scenario['id']} {run_tag}",
                kind="fictional_sample",
                last_reviewed_on=date(2026, 1, 1),
            )
            session.add(source)
            await session.flush()

            profile = Profile(
                slug=f"parity_{scenario['id']}_{run_tag}",
                display_name=f"Parity {scenario['id']}",
                is_demo=False,
            )
            session.add(profile)
            await session.flush()

            card_id_map: dict[int, int] = {}
            rule_id_map: dict[int, int] = {}

            for raw_card in scenario["cards"]:
                curr = await _get_or_create_currency(
                    session, raw_card["reward_currency"], curr_cache
                )
                product = CardProduct(
                    issuer_name=f"Parity Issuer {run_tag}",
                    name=f"{raw_card['card_name']} {raw_card['card_id']} {run_tag}",
                    reward_currency_id=curr.id,
                    annual_fee_cents=0,
                    network_label="TestNet",
                )
                session.add(product)
                await session.flush()

                pc = ProfileCard(
                    profile_id=profile.id,
                    card_product_id=product.id,
                    nickname=raw_card["card_name"],
                    opened_on=date(2025, 1, 1),
                    is_active=True,
                )
                session.add(pc)
                await session.flush()
                card_id_map[pc.id] = raw_card["card_id"]

                caps_by_key: dict[str, SpendCap] = {}
                for raw_cap in raw_card.get("caps", ()):
                    db_cap = SpendCap(
                        cap_group_key=raw_cap["cap_group_key"],
                        card_product_id=product.id,
                        cap_amount_cents=raw_cap["cap_amount_cents"],
                        period=raw_cap["period"],
                    )
                    session.add(db_cap)
                    await session.flush()
                    caps_by_key[raw_cap["cap_group_key"]] = db_cap

                for raw_rule in sorted(raw_card["rules"], key=lambda r: r["id"]):
                    cat_id = None
                    if raw_rule.get("category"):
                        cat = await _get_or_create_category(
                            session, raw_rule["category"], cat_cache
                        )
                        cat_id = cat.id
                    merch_id = None
                    if raw_rule.get("merchant"):
                        merch = await _get_or_create_merchant(
                            session, raw_rule["merchant"], merch_cache
                        )
                        merch_id = merch.id
                    cap_key = raw_rule.get("cap_group_key")
                    db_rule = EarningRule(
                        rule_key=f"{raw_rule['rule_key']}.c{raw_card['card_id']}.{run_tag}",
                        version=raw_rule["version"],
                        card_product_id=product.id,
                        reward_currency_id=curr.id,
                        scope_type=raw_rule["scope_type"],
                        category_id=cat_id,
                        merchant_id=merch_id,
                        multiplier=Decimal(raw_rule["multiplier"]),
                        priority=raw_rule.get("priority", 0),
                        cap_id=caps_by_key[cap_key].id if cap_key else None,
                        post_cap_behavior=raw_rule.get("post_cap_behavior", "fallback_to_base"),
                        min_transaction_cents=raw_rule.get("min_transaction_cents"),
                        min_period_spend_cents=raw_rule.get("min_period_spend_cents"),
                        threshold_period=raw_rule.get("threshold_period"),
                        rounding=raw_rule.get("rounding", "floor_units"),
                        effective_from=date.fromisoformat(raw_rule["effective_from"]),
                        effective_to=(
                            date.fromisoformat(raw_rule["effective_to"])
                            if raw_rule.get("effective_to")
                            else None
                        ),
                        source_id=source.id,
                        last_reviewed_on=date(2026, 1, 1),
                    )
                    session.add(db_rule)
                    await session.flush()
                    rule_id_map[db_rule.id] = raw_rule["id"]

                    for raw_ex in raw_rule.get("exclusions", ()):
                        ex_type = raw_ex["exclusion_type"]
                        ex_cat_id = None
                        ex_merch_id = None
                        ex_tag = None
                        if ex_type == "category":
                            ex_cat = await _get_or_create_category(
                                session, raw_ex["target"], cat_cache
                            )
                            ex_cat_id = ex_cat.id
                        elif ex_type == "merchant":
                            ex_merch = await _get_or_create_merchant(
                                session, raw_ex["target"], merch_cache
                            )
                            ex_merch_id = ex_merch.id
                        else:
                            ex_tag = raw_ex["target"]
                        session.add(
                            RuleExclusion(
                                rule_id=db_rule.id,
                                exclusion_type=ex_type,
                                target_category_id=ex_cat_id,
                                target_merchant_id=ex_merch_id,
                                target_tag=ex_tag,
                                reason=raw_ex["reason"],
                            )
                        )

                raw_val = raw_card.get("valuation")
                if raw_val is not None:
                    val_curr = await _get_or_create_currency(
                        session, raw_val["reward_currency"], curr_cache
                    )
                    existing_val = await session.scalar(
                        select(CurrencyValuation).where(
                            CurrencyValuation.profile_id == profile.id,
                            CurrencyValuation.reward_currency_id == val_curr.id,
                        )
                    )
                    if existing_val is None:
                        session.add(
                            CurrencyValuation(
                                profile_id=profile.id,
                                reward_currency_id=val_curr.id,
                                cents_per_unit=Decimal(raw_val["cents_per_unit"]),
                                is_user_set=bool(raw_val.get("is_user_set", True)),
                            )
                        )

                spend_history = raw_card.get("spend_history", {})
                tx_amounts: list[int] = list(
                    spend_history.get("cap_spend_cents", {}).values()
                ) + list(spend_history.get("threshold_spend_cents", {}).values())
                for amt in tx_amounts:
                    if amt > 0:
                        session.add(
                            Transaction(
                                profile_id=profile.id,
                                profile_card_id=pc.id,
                                amount_cents=amt,
                                category_id=purchase_cat.id,
                                occurred_on=purchase.purchase_date,
                            )
                        )

            await session.flush()

            assembled = await assemble_profile_engine_inputs(
                session, profile.id, purchase.purchase_date
            )
            evaluations = [
                evaluate_purchase(
                    purchase=purchase,
                    card=item.card,
                    spend_history=item.spend_history,
                    valuation=item.valuation,
                )
                for item in assembled
            ]
            result = rank_card_evaluations(evaluations)

            expected = scenario["expected"]
            assert len(result.ranked) == len(expected["ranked"])
            for act, exp in zip(result.ranked, expected["ranked"], strict=True):
                _assert_db_card_matches(act, exp, card_id_map, rule_id_map)

            assert len(result.unranked) == len(expected["unranked"])
            for act, exp in zip(result.unranked, expected["unranked"], strict=True):
                _assert_db_card_matches(act, exp, card_id_map, rule_id_map)

            assert len(result.ineligible) == len(expected["ineligible"])
            for act, exp in zip(result.ineligible, expected["ineligible"], strict=True):
                _assert_db_card_matches(act, exp, card_id_map, rule_id_map)

            if "global_notes" in expected:
                assert result.global_notes == tuple(expected["global_notes"])
        finally:
            await session.rollback()


@pytest.mark.asyncio
async def test_spend_history_includes_on_purchase_date_excludes_after_purchase_date() -> None:
    """Transactions on purchase_date are included in cap/threshold spend; future ones are not."""
    await close_engine()
    session_factory = get_session_maker()
    run_tag = uuid4().hex[:8]
    purchase_date = date(2026, 8, 15)

    async with session_factory() as session:
        try:
            cat = await _get_or_create_category(session, "dining", {})
            curr = await _get_or_create_currency(session, "NW_CASH", {})
            source = RuleSource(
                title=f"Date Boundary Source {run_tag}",
                kind="fictional_sample",
                last_reviewed_on=date(2026, 1, 1),
            )
            session.add(source)
            await session.flush()

            product = CardProduct(
                issuer_name=f"Boundary Issuer {run_tag}",
                name=f"Boundary Card {run_tag}",
                reward_currency_id=curr.id,
                annual_fee_cents=0,
                network_label="TestNet",
            )
            session.add(product)
            await session.flush()

            cap = SpendCap(
                cap_group_key="dining_q",
                card_product_id=product.id,
                cap_amount_cents=50000,
                period="quarterly",
            )
            session.add(cap)
            await session.flush()

            session.add(
                EarningRule(
                    rule_key=f"boundary.dining.{run_tag}",
                    version=1,
                    card_product_id=product.id,
                    reward_currency_id=curr.id,
                    scope_type="category",
                    category_id=cat.id,
                    multiplier=Decimal("5.0000"),
                    cap_id=cap.id,
                    min_period_spend_cents=10000,
                    threshold_period="quarterly",
                    effective_from=date(2026, 1, 1),
                    source_id=source.id,
                    last_reviewed_on=date(2026, 1, 1),
                )
            )

            profile = Profile(
                slug=f"boundary_{run_tag}",
                display_name="Boundary Test",
                is_demo=False,
            )
            session.add(profile)
            await session.flush()

            pc = ProfileCard(
                profile_id=profile.id,
                card_product_id=product.id,
                nickname="Boundary Card",
                opened_on=date(2025, 1, 1),
                is_active=True,
            )
            session.add(pc)
            await session.flush()

            # Before purchase_date (included)
            session.add(
                Transaction(
                    profile_id=profile.id,
                    profile_card_id=pc.id,
                    amount_cents=10000,
                    category_id=cat.id,
                    occurred_on=purchase_date - timedelta(days=5),
                )
            )
            # On purchase_date (included)
            session.add(
                Transaction(
                    profile_id=profile.id,
                    profile_card_id=pc.id,
                    amount_cents=15000,
                    category_id=cat.id,
                    occurred_on=purchase_date,
                )
            )
            # After purchase_date (excluded)
            session.add(
                Transaction(
                    profile_id=profile.id,
                    profile_card_id=pc.id,
                    amount_cents=30000,
                    category_id=cat.id,
                    occurred_on=purchase_date + timedelta(days=1),
                )
            )
            await session.flush()

            assembled = await assemble_profile_engine_inputs(session, profile.id, purchase_date)
            assert len(assembled) == 1
            assert assembled[0].spend_history.cap_spend_cents == {"dining_q": 25000}
            assert assembled[0].spend_history.threshold_spend_cents == {"quarterly": 25000}
        finally:
            await session.rollback()
