"""Unit tests for reward engine cap handling, straddle, and fallback (T14, AC-5).

Validates full-within-cap allocation, exact cap exhaustion, pre-exhausted cap
fallback, AC-5 cap straddle, multiple successive exhausted cap groups, missing
cap configuration error, no-eligible-fallback unallocated remainder, determinism,
and runtime immutability.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine.caps import (
    CapAllocationResult,
    CapPortion,
    allocate_purchase_across_caps,
)
from app.engine.types import (
    EarningRule,
    Period,
    Purchase,
    ScopeType,
    SpendCap,
    SpendHistory,
)


def _make_rule(
    id: int,
    rule_key: str,
    scope_type: ScopeType,
    multiplier: str,
    category: str | None = None,
    merchant: str | None = None,
    priority: int = 0,
    cap_group_key: str | None = None,
    min_period_spend_cents: int | None = None,
    threshold_period: Period | None = None,
) -> EarningRule:
    return EarningRule(
        id=id,
        rule_key=rule_key,
        version=1,
        scope_type=scope_type,
        multiplier=Decimal(multiplier),
        effective_from=date(2026, 1, 1),
        category=category,
        merchant=merchant,
        priority=priority,
        cap_group_key=cap_group_key,
        min_period_spend_cents=min_period_spend_cents,
        threshold_period=threshold_period,
    )


def _make_purchase(
    amount_cents: int,
    category: str = "dining",
    merchant: str | None = None,
) -> Purchase:
    return Purchase(
        amount_cents=amount_cents,
        category=category,
        purchase_date=date(2026, 11, 15),
        merchant=merchant,
    )


class TestCapAllocation:
    """Tests for cap allocation, straddle, and iterative fallback."""

    def test_ac5_cap_straddle_splits_between_capped_and_base_rule(self) -> None:
        """AC-5: 5x rule ($500 cap, $450 spent) + 1x base on $100 purchase -> $50 @ 5x, $50 @ 1x."""
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x_q",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_quarterly",
        )
        base_rule = _make_rule(
            id=2,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(
            cap_group_key="dining_quarterly",
            cap_amount_cents=50000,
            period=Period.QUARTERLY,
        )
        history = SpendHistory(cap_spend_cents={"dining_quarterly": 45000})
        purchase = _make_purchase(amount_cents=10000, category="dining")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule, base_rule),
            caps=(cap,),
            spend_history=history,
        )

        assert isinstance(result, CapAllocationResult)
        assert result.unallocated_cents == 0
        assert result.portions == (
            CapPortion(rule=promo_rule, amount_cents=5000, cap_group_key="dining_quarterly"),
            CapPortion(rule=base_rule, amount_cents=5000, cap_group_key=None),
        )
        assert [t.step_number for t in result.trace_steps] == [1, 2]
        assert result.trace_steps[0].rule_id == 1
        assert result.trace_steps[0].action == "allocated"
        assert result.trace_steps[1].rule_id == 2
        assert result.trace_steps[1].action == "allocated"

    def test_purchase_entirely_within_remaining_cap(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_q",
        )
        base_rule = _make_rule(
            id=2,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        history = SpendHistory(cap_spend_cents={"dining_q": 10000})
        purchase = _make_purchase(amount_cents=15000, category="dining")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule, base_rule),
            caps=(cap,),
            spend_history=history,
        )

        assert result.unallocated_cents == 0
        assert result.portions == (
            CapPortion(rule=promo_rule, amount_cents=15000, cap_group_key="dining_q"),
        )
        assert len(result.trace_steps) == 1

    def test_cap_exactly_exhausted_no_fallback_needed(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_q",
        )
        base_rule = _make_rule(
            id=2,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        history = SpendHistory(cap_spend_cents={"dining_q": 40000})
        purchase = _make_purchase(amount_cents=10000, category="dining")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule, base_rule),
            caps=(cap,),
            spend_history=history,
        )

        assert result.unallocated_cents == 0
        assert result.portions == (
            CapPortion(rule=promo_rule, amount_cents=10000, cap_group_key="dining_q"),
        )

    def test_cap_already_exhausted_before_purchase_falls_back_to_base(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_q",
        )
        base_rule = _make_rule(
            id=2,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        # Prior spend exceeds cap (>= cap_amount_cents)
        history = SpendHistory(cap_spend_cents={"dining_q": 55000})
        purchase = _make_purchase(amount_cents=8000, category="dining")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule, base_rule),
            caps=(cap,),
            spend_history=history,
        )

        assert result.unallocated_cents == 0
        assert result.portions == (
            CapPortion(rule=base_rule, amount_cents=8000, cap_group_key=None),
        )
        assert [t.action for t in result.trace_steps] == ["cap_exhausted", "allocated"]
        assert result.trace_steps[0].reason == "cap_exhausted"
        assert result.trace_steps[0].rule_id == 1
        assert result.trace_steps[1].rule_id == 2

    def test_missing_cap_configuration_raises_value_error(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="missing_cap_key",
        )
        purchase = _make_purchase(amount_cents=5000, category="dining")

        with pytest.raises(ValueError, match="missing_cap_key"):
            allocate_purchase_across_caps(
                purchase=purchase,
                rules=(promo_rule,),
                caps=(),
                spend_history=SpendHistory(),
            )

    def test_multiple_successive_exhausted_cap_groups_and_partial_straddle(self) -> None:
        """Merchant 6x (exhausted) -> Category 4x ($30 remaining) -> Base 1x (remainder)."""
        merchant_rule = _make_rule(
            id=1,
            rule_key="bistro.6x",
            scope_type=ScopeType.MERCHANT,
            merchant="Acme Bistro",
            multiplier="6.0",
            cap_group_key="merchant_cap",
        )
        category_rule = _make_rule(
            id=2,
            rule_key="dining.4x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="4.0",
            cap_group_key="dining_cap",
        )
        base_rule = _make_rule(
            id=3,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        caps = (
            SpendCap(cap_group_key="merchant_cap", cap_amount_cents=10000, period=Period.MONTHLY),
            SpendCap(cap_group_key="dining_cap", cap_amount_cents=20000, period=Period.QUARTERLY),
        )
        history = SpendHistory(
            cap_spend_cents={
                "merchant_cap": 10000,  # 0 remaining
                "dining_cap": 17000,  # 3000 ($30) remaining
            }
        )
        purchase = _make_purchase(amount_cents=10000, category="dining", merchant="Acme Bistro")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(base_rule, category_rule, merchant_rule),
            caps=caps,
            spend_history=history,
        )

        assert result.unallocated_cents == 0
        assert result.portions == (
            CapPortion(rule=category_rule, amount_cents=3000, cap_group_key="dining_cap"),
            CapPortion(rule=base_rule, amount_cents=7000, cap_group_key=None),
        )
        assert [t.step_number for t in result.trace_steps] == [1, 2, 3]
        assert [t.action for t in result.trace_steps] == [
            "cap_exhausted",
            "allocated",
            "allocated",
        ]
        assert [t.rule_id for t in result.trace_steps] == [1, 2, 3]

    def test_no_eligible_fallback_leaves_explicit_unallocated_remainder(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_q",
        )
        cap = SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        history = SpendHistory(cap_spend_cents={"dining_q": 47000})  # 3000 remaining
        purchase = _make_purchase(amount_cents=10000, category="dining")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule,),
            caps=(cap,),
            spend_history=history,
        )

        assert result.portions == (
            CapPortion(rule=promo_rule, amount_cents=3000, cap_group_key="dining_q"),
        )
        assert result.unallocated_cents == 7000
        assert [t.action for t in result.trace_steps] == ["allocated", "unallocated"]
        assert result.trace_steps[1].reason == "no_fallback_rule"

    def test_determinism_and_immutability(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_q",
        )
        base_rule = _make_rule(
            id=2,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        history = SpendHistory(cap_spend_cents={"dining_q": 45000})
        purchase = _make_purchase(amount_cents=10000, category="dining")

        r1 = allocate_purchase_across_caps(purchase, (promo_rule, base_rule), (cap,), history)
        r2 = allocate_purchase_across_caps(purchase, (base_rule, promo_rule), (cap,), history)

        assert r1 == r2
        with pytest.raises(AttributeError):
            r1.unallocated_cents = 100  # type: ignore[misc]
        with pytest.raises(TypeError, match="set"):
            CapAllocationResult(portions={r1.portions[0]})  # type: ignore[arg-type]

    def test_non_winning_applicable_rule_with_missing_cap_raises_value_error(self) -> None:
        """Missing cap on any applicable rule fails even if another rule covers the purchase."""
        merchant_rule = _make_rule(
            id=1,
            rule_key="bistro.6x",
            scope_type=ScopeType.MERCHANT,
            merchant="Acme Bistro",
            multiplier="6.0",
            cap_group_key="valid_cap",
        )
        dining_rule = _make_rule(
            id=2,
            rule_key="dining.4x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="4.0",
            cap_group_key="missing_cap",
        )
        cap = SpendCap(cap_group_key="valid_cap", cap_amount_cents=50000, period=Period.QUARTERLY)
        purchase = _make_purchase(amount_cents=5000, category="dining", merchant="Acme Bistro")

        with pytest.raises(ValueError, match="missing_cap"):
            allocate_purchase_across_caps(
                purchase=purchase,
                rules=(merchant_rule, dining_rule),
                caps=(cap,),
                spend_history=SpendHistory(),
            )

    def test_shared_cap_group_excludes_other_rules_in_same_group_after_straddle(self) -> None:
        """Two rules sharing one cap_group_key cannot reuse the cap after it is straddled."""
        merchant_rule = _make_rule(
            id=1,
            rule_key="bistro.5x",
            scope_type=ScopeType.MERCHANT,
            merchant="Acme Bistro",
            multiplier="5.0",
            cap_group_key="shared_q",
        )
        category_rule = _make_rule(
            id=2,
            rule_key="dining.3x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="3.0",
            cap_group_key="shared_q",
        )
        base_rule = _make_rule(
            id=3,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(cap_group_key="shared_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        history = SpendHistory(cap_spend_cents={"shared_q": 47000})  # 3000 remaining
        purchase = _make_purchase(amount_cents=10000, category="dining", merchant="Acme Bistro")

        result = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(merchant_rule, category_rule, base_rule),
            caps=(cap,),
            spend_history=history,
        )

        assert result.unallocated_cents == 0
        assert result.portions == (
            CapPortion(rule=merchant_rule, amount_cents=3000, cap_group_key="shared_q"),
            CapPortion(rule=base_rule, amount_cents=7000, cap_group_key=None),
        )

    def test_duplicate_cap_definitions_raise_value_error(self) -> None:
        cap1 = SpendCap(cap_group_key="dup_cap", cap_amount_cents=50000, period=Period.QUARTERLY)
        cap2 = SpendCap(cap_group_key="dup_cap", cap_amount_cents=25000, period=Period.MONTHLY)
        base_rule = _make_rule(
            id=1, rule_key="base.1x", scope_type=ScopeType.BASE, multiplier="1.0"
        )
        purchase = _make_purchase(amount_cents=1000)

        with pytest.raises(ValueError, match="Duplicate cap_group_key"):
            allocate_purchase_across_caps(purchase, (base_rule,), (cap1, cap2), SpendHistory())

    def test_empty_rules_returns_full_amount_unallocated(self) -> None:
        purchase = _make_purchase(amount_cents=4200)

        result = allocate_purchase_across_caps(purchase, (), (), SpendHistory())

        assert result.portions == ()
        assert result.unallocated_cents == 4200
        assert len(result.trace_steps) == 1
        assert result.trace_steps[0].action == "unallocated"
        assert result.trace_steps[0].reason == "no_fallback_rule"

    def test_cap_allocation_result_rejects_negative_and_bool_unallocated_cents(self) -> None:
        with pytest.raises(ValueError, match="non-negative integer"):
            CapAllocationResult(portions=(), unallocated_cents=-1)
        with pytest.raises(ValueError, match="non-negative integer"):
            CapAllocationResult(portions=(), unallocated_cents=True)

    def test_cap_portion_rejects_zero_and_negative_amount_cents(self) -> None:
        rule = _make_rule(id=1, rule_key="base.1x", scope_type=ScopeType.BASE, multiplier="1.0")
        with pytest.raises(ValueError, match="strictly positive"):
            CapPortion(rule=rule, amount_cents=0)
        with pytest.raises(ValueError, match="strictly positive"):
            CapPortion(rule=rule, amount_cents=-50)

    def test_cap_allocation_enforces_period_spend_threshold_before_selection_and_caps(self) -> None:
        """Threshold rule below prior spend is rejected before cap allocation; fallback wins."""
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.tier2_5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            cap_group_key="dining_q",
            min_period_spend_cents=100000,
            threshold_period=Period.CALENDAR_YEAR,
        )
        base_rule = _make_rule(
            id=2,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        cap = SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY)
        purchase = _make_purchase(amount_cents=60000, category="dining")

        # Prior spend $500 < $1000 threshold (even though $500 + $600 >= $1000): fallback wins
        below_history = SpendHistory(
            cap_spend_cents={"dining_q": 0},
            threshold_spend_cents={"calendar_year": 50000},
        )
        res_below = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule, base_rule),
            caps=(cap,),
            spend_history=below_history,
        )
        assert res_below.unallocated_cents == 0
        assert res_below.portions == (
            CapPortion(rule=base_rule, amount_cents=60000, cap_group_key=None),
        )

        # Prior spend $1000 == $1000 threshold: promo rule qualifies and straddles $500 cap
        at_history = SpendHistory(
            cap_spend_cents={"dining_q": 0},
            threshold_spend_cents={"calendar_year": 100000},
        )
        res_at = allocate_purchase_across_caps(
            purchase=purchase,
            rules=(promo_rule, base_rule),
            caps=(cap,),
            spend_history=at_history,
        )
        assert res_at.unallocated_cents == 0
        assert res_at.portions == (
            CapPortion(rule=promo_rule, amount_cents=50000, cap_group_key="dining_q"),
            CapPortion(rule=base_rule, amount_cents=10000, cap_group_key=None),
        )
