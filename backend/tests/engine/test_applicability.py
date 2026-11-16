"""Unit tests for reward engine applicability and exclusion rules (T10, AC-4).

Validates scope matching (BASE, CATEGORY, MERCHANT), merchant presence checks,
exclusion matching (category, merchant, merchant_tag), case/whitespace normalization,
precedence rules, order preservation, and rejection trace step generation.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine.applicability import (
    ApplicabilityResult,
    check_rule_applicability,
    filter_applicable_rules,
)
from app.engine.selection import select_best_rule
from app.engine.types import (
    EarningRule,
    ExclusionType,
    Period,
    Purchase,
    RuleExclusion,
    ScopeType,
    SpendHistory,
)


def _make_rule(
    id: int,
    rule_key: str,
    scope_type: ScopeType,
    category: str | None = None,
    merchant: str | None = None,
    exclusions: tuple[RuleExclusion, ...] = (),
    multiplier: str = "1.0",
    priority: int = 0,
    min_transaction_cents: int | None = None,
    min_period_spend_cents: int | None = None,
    threshold_period: Period | None = None,
) -> EarningRule:
    """Helper to construct an EarningRule for applicability testing."""
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
        min_transaction_cents=min_transaction_cents,
        min_period_spend_cents=min_period_spend_cents,
        threshold_period=threshold_period,
        exclusions=exclusions,
    )


def _make_purchase(
    category: str = "dining",
    merchant: str | None = None,
    merchant_tags: tuple[str, ...] = (),
    amount_cents: int = 10000,
) -> Purchase:
    """Helper to construct a Purchase for applicability testing."""
    return Purchase(
        amount_cents=amount_cents,
        category=category,
        purchase_date=date(2026, 11, 15),
        merchant=merchant,
        merchant_tags=merchant_tags,
    )


class TestScopeMatching:
    """Tests for BASE, CATEGORY, and MERCHANT scope matching."""

    def test_base_scope_matches_any_purchase(self) -> None:
        base_rule = _make_rule(1, "base.standard", ScopeType.BASE)

        p1 = _make_purchase(category="dining")
        p2 = _make_purchase(category="groceries", merchant="Acme Mart")
        p3 = _make_purchase(category="travel", merchant="FlyAir", merchant_tags=("airline",))

        res1 = check_rule_applicability(base_rule, p1)
        res2 = check_rule_applicability(base_rule, p2)
        res3 = check_rule_applicability(base_rule, p3)

        assert res1.is_applicable is True
        assert res1.rejection_reason is None
        assert res2.is_applicable is True
        assert res3.is_applicable is True

    def test_category_scope_match_and_mismatch(self) -> None:
        dining_rule = _make_rule(2, "dining.3x", ScopeType.CATEGORY, category="dining")

        p_match = _make_purchase(category="dining")
        p_mismatch = _make_purchase(category="groceries")

        res_match = check_rule_applicability(dining_rule, p_match)
        res_mismatch = check_rule_applicability(dining_rule, p_mismatch)

        assert isinstance(res_match, ApplicabilityResult)
        assert res_match.is_applicable is True

        assert res_mismatch.is_applicable is False
        assert res_mismatch.rejection_reason == "category_mismatch"
        assert res_mismatch.rejection_detail is not None
        assert "groceries" in res_mismatch.rejection_detail
        assert "dining" in res_mismatch.rejection_detail

    def test_merchant_scope_match_and_mismatch(self) -> None:
        coffee_rule = _make_rule(3, "coffee.5x", ScopeType.MERCHANT, merchant="Acme Coffee")

        p_match = _make_purchase(category="dining", merchant="Acme Coffee")
        p_mismatch = _make_purchase(category="dining", merchant="Other Cafe")

        res_match = check_rule_applicability(coffee_rule, p_match)
        res_mismatch = check_rule_applicability(coffee_rule, p_mismatch)

        assert res_match.is_applicable is True

        assert res_mismatch.is_applicable is False
        assert res_mismatch.rejection_reason == "merchant_mismatch"
        assert "Other Cafe" in res_mismatch.rejection_detail  # type: ignore[operator]
        assert "Acme Coffee" in res_mismatch.rejection_detail  # type: ignore[operator]

    def test_merchant_scope_missing_merchant(self) -> None:
        coffee_rule = _make_rule(3, "coffee.5x", ScopeType.MERCHANT, merchant="Acme Coffee")
        p_no_merchant = _make_purchase(category="dining", merchant=None)

        res = check_rule_applicability(coffee_rule, p_no_merchant)

        assert res.is_applicable is False
        assert res.rejection_reason == "missing_merchant"
        assert "no merchant specified" in res.rejection_detail  # type: ignore[operator]

    def test_scope_case_and_whitespace_normalization(self) -> None:
        cat_rule = _make_rule(4, "cat.norm", ScopeType.CATEGORY, category="  Dining  ")
        p_cat = _make_purchase(category="DINING")

        merch_rule = _make_rule(5, "merch.norm", ScopeType.MERCHANT, merchant="  Acme Coffee  ")
        p_merch = _make_purchase(category="dining", merchant="acme coffee")

        assert check_rule_applicability(cat_rule, p_cat).is_applicable is True
        assert check_rule_applicability(merch_rule, p_merch).is_applicable is True


class TestExclusionMatching:
    """Tests for AC-4 category, merchant, and merchant-tag exclusions."""

    def test_merchant_tag_exclusion_ac4(self) -> None:
        """SPEC AC-4: Grocery 4x rule excluding warehouse-club merchants."""
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="warehouse_club",
            reason="Warehouse clubs excluded from grocery bonus",
        )
        grocery_rule = _make_rule(
            id=10,
            rule_key="grocery.4x",
            scope_type=ScopeType.CATEGORY,
            category="groceries",
            exclusions=(exclusion,),
            multiplier="4.0",
        )

        p_regular = _make_purchase(
            category="groceries",
            merchant="SuperFoods",
            merchant_tags=("supermarket",),
        )
        p_warehouse = _make_purchase(
            category="groceries",
            merchant="Wholesale Club",
            merchant_tags=("warehouse_club", "big_box"),
        )

        res_regular = check_rule_applicability(grocery_rule, p_regular)
        res_warehouse = check_rule_applicability(grocery_rule, p_warehouse)

        assert res_regular.is_applicable is True

        assert res_warehouse.is_applicable is False
        assert res_warehouse.rejection_reason == "merchant_tag_exclusion"
        assert res_warehouse.matched_exclusion == exclusion
        assert "Warehouse clubs excluded from grocery bonus" in res_warehouse.rejection_detail  # type: ignore[operator]

    def test_category_exclusion(self) -> None:
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.CATEGORY,
            target="gift_cards",
            reason="Gift card category excluded",
        )
        base_rule = _make_rule(
            id=1,
            rule_key="base.with_ex",
            scope_type=ScopeType.BASE,
            exclusions=(exclusion,),
        )

        p_gift = _make_purchase(category="gift_cards")
        p_other = _make_purchase(category="dining")

        res_gift = check_rule_applicability(base_rule, p_gift)
        res_other = check_rule_applicability(base_rule, p_other)

        assert res_gift.is_applicable is False
        assert res_gift.rejection_reason == "category_exclusion"
        assert res_gift.matched_exclusion == exclusion
        assert "Gift card category excluded" in res_gift.rejection_detail  # type: ignore[operator]
        assert res_other.is_applicable is True

    def test_merchant_exclusion(self) -> None:
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT,
            target="Excluded Gas Co",
            reason="Specific merchant excluded from gas rewards",
        )
        gas_rule = _make_rule(
            id=20,
            rule_key="gas.3x",
            scope_type=ScopeType.CATEGORY,
            category="gas",
            exclusions=(exclusion,),
        )

        p_ex = _make_purchase(category="gas", merchant="Excluded Gas Co")
        p_ok = _make_purchase(category="gas", merchant="Clean Fuel Co")

        res_ex = check_rule_applicability(gas_rule, p_ex)
        res_ok = check_rule_applicability(gas_rule, p_ok)

        assert res_ex.is_applicable is False
        assert res_ex.rejection_reason == "merchant_exclusion"
        assert res_ex.matched_exclusion == exclusion
        assert res_ok.is_applicable is True

    def test_exclusion_case_and_whitespace_normalization(self) -> None:
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="  Warehouse_Club  ",
            reason="Warehouse excluded",
        )
        rule = _make_rule(
            id=10,
            rule_key="norm.ex",
            scope_type=ScopeType.BASE,
            exclusions=(exclusion,),
        )
        p = _make_purchase(category="groceries", merchant_tags=("WAREHOUSE_CLUB",))

        res = check_rule_applicability(rule, p)
        assert res.is_applicable is False
        assert res.rejection_reason == "merchant_tag_exclusion"

    def test_multiple_matching_exclusions_first_match_wins(self) -> None:
        """When multiple exclusions match, the first defined exclusion wins deterministically."""
        ex1 = RuleExclusion(
            exclusion_type=ExclusionType.CATEGORY,
            target="dining",
            reason="Dining category excluded (first exclusion)",
        )
        ex2 = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="sit_down",
            reason="Sit down tag excluded (second exclusion)",
        )
        rule = _make_rule(
            id=15,
            rule_key="multi.ex",
            scope_type=ScopeType.BASE,
            exclusions=(ex1, ex2),
        )

        # Purchase matches both category ('dining') and merchant tag ('sit_down')
        purchase = _make_purchase(category="dining", merchant_tags=("sit_down",))
        res = check_rule_applicability(rule, purchase)

        assert res.is_applicable is False
        assert res.rejection_reason == "category_exclusion"
        assert res.matched_exclusion == ex1
        assert "Dining category excluded (first exclusion)" in (res.rejection_detail or "")

    def test_empty_exclusion_target_or_empty_tag_does_not_match(self) -> None:
        """Empty or whitespace-only exclusion targets and empty tags do not cause false matches."""
        empty_ex = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="   ",
            reason="Empty exclusion target",
        )
        rule = _make_rule(
            id=16,
            rule_key="empty.target",
            scope_type=ScopeType.BASE,
            exclusions=(empty_ex,),
        )

        # Purchase with empty string tag and normal category
        purchase = _make_purchase(category="dining", merchant_tags=("", "fast_food"))
        res = check_rule_applicability(rule, purchase)

        assert res.is_applicable is True
        assert res.rejection_reason is None


class TestPrecedenceAndCombinedEvaluation:
    """Tests for scope check precedence over exclusions."""

    def test_scope_mismatch_precedes_exclusions(self) -> None:
        """When scope does not match, return scope mismatch without evaluating exclusions."""
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="warehouse_club",
            reason="Warehouse tag excluded",
        )
        travel_rule = _make_rule(
            id=5,
            rule_key="travel.5x",
            scope_type=ScopeType.CATEGORY,
            category="travel",
            exclusions=(exclusion,),
        )
        # Purchase is groceries (mismatch) AND has warehouse_club tag
        purchase = _make_purchase(category="groceries", merchant_tags=("warehouse_club",))

        res = check_rule_applicability(travel_rule, purchase)

        assert res.is_applicable is False
        assert res.rejection_reason == "category_mismatch"
        assert res.matched_exclusion is None


class TestBatchFilterApplicableRules:
    """Tests for filter_applicable_rules and trace step generation."""

    def test_filters_rules_and_preserves_order(self) -> None:
        p = _make_purchase(
            category="dining",
            merchant="Acme Bistro",
            merchant_tags=("sit_down",),
        )

        # r1: category matches (dining) -> applicable
        r1 = _make_rule(1, "dining.cat", ScopeType.CATEGORY, category="dining")
        # r2: category mismatch (groceries) -> rejected
        r2 = _make_rule(2, "groceries.cat", ScopeType.CATEGORY, category="groceries")
        # r3: merchant matches (Acme Bistro) -> applicable
        r3 = _make_rule(3, "bistro.merch", ScopeType.MERCHANT, merchant="Acme Bistro")
        # r4: base scope with sit_down exclusion -> rejected
        ex = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="sit_down",
            reason="Sit-down restaurants excluded from quick-pay",
        )
        r4 = _make_rule(4, "base.ex", ScopeType.BASE, exclusions=(ex,))
        # r5: standard base scope -> applicable
        r5 = _make_rule(5, "base.std", ScopeType.BASE)

        rules = (r1, r2, r3, r4, r5)
        applicable, rejection_traces = filter_applicable_rules(rules, p)

        # 1. Surviving applicable rules preserve input order
        assert applicable == (r1, r3, r5)
        assert [r.id for r in applicable] == [1, 3, 5]

        # 2. Rejection traces generated in order for rejected rules (r2, r4)
        assert len(rejection_traces) == 2

        t1, t2 = rejection_traces
        assert t1.step_number == 1
        assert t1.step_type == "applicability_filter"
        assert t1.action == "rejected"
        assert t1.rule_id == 2
        assert t1.rule_key == "groceries.cat"
        assert t1.reason == "category_mismatch"
        assert "groceries" in t1.detail

        assert t2.step_number == 2
        assert t2.step_type == "applicability_filter"
        assert t2.action == "rejected"
        assert t2.rule_id == 4
        assert t2.rule_key == "base.ex"
        assert t2.reason == "merchant_tag_exclusion"
        assert "Sit-down restaurants excluded from quick-pay" in t2.detail

    def test_all_applicable_and_all_rejected(self) -> None:
        p = _make_purchase(category="dining")
        base1 = _make_rule(1, "base.1", ScopeType.BASE)
        base2 = _make_rule(2, "base.2", ScopeType.BASE)

        # All applicable
        app_all, traces_empty = filter_applicable_rules((base1, base2), p)
        assert app_all == (base1, base2)
        assert traces_empty == ()

        # All rejected
        gas1 = _make_rule(3, "gas.1", ScopeType.CATEGORY, category="gas")
        gas2 = _make_rule(4, "gas.2", ScopeType.CATEGORY, category="gas")
        app_none, traces_all = filter_applicable_rules((gas1, gas2), p)
        assert app_none == ()
        assert len(traces_all) == 2

    def test_empty_rules_input(self) -> None:
        p = _make_purchase()
        app_empty, traces_empty = filter_applicable_rules((), p)
        assert app_empty == ()
        assert traces_empty == ()


class TestMinTransactionThreshold:
    """Tests for per-transaction minimum threshold enforcement (T12, AC-7)."""

    def test_no_threshold_passes_for_small_purchase(self) -> None:
        rule = _make_rule(
            id=20,
            rule_key="dining.no_min",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=None,
        )
        purchase = _make_purchase(category="dining", amount_cents=1)

        res = check_rule_applicability(rule, purchase)

        assert res.is_applicable is True
        assert res.rejection_reason is None
        assert res.rejection_detail is None

    def test_below_minimum_threshold_rejected(self) -> None:
        rule = _make_rule(
            id=21,
            rule_key="dining.min25",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=2500,
        )
        purchase = _make_purchase(category="dining", amount_cents=2000)

        res = check_rule_applicability(rule, purchase)

        assert res.is_applicable is False
        assert res.rejection_reason == "below_min_transaction"
        assert res.matched_exclusion is None
        assert res.rejection_detail is not None
        assert "$20.00" in res.rejection_detail
        assert "$25.00" in res.rejection_detail
        assert "2000" in res.rejection_detail
        assert "2500" in res.rejection_detail

    def test_threshold_rejection_detail_formats_dollars_accurately(self) -> None:
        cases = (
            (1, 100, "$0.01", "$1.00"),
            (99, 10025, "$0.99", "$100.25"),
        )
        for purchase_cents, min_cents, expected_purchase, expected_min in cases:
            rule = _make_rule(
                id=25,
                rule_key="dining.format_check",
                scope_type=ScopeType.CATEGORY,
                category="dining",
                min_transaction_cents=min_cents,
            )
            purchase = _make_purchase(category="dining", amount_cents=purchase_cents)

            res = check_rule_applicability(rule, purchase)

            assert res.is_applicable is False
            assert res.rejection_reason == "below_min_transaction"
            assert res.rejection_detail is not None
            assert expected_purchase in res.rejection_detail
            assert expected_min in res.rejection_detail


class TestPeriodSpendThreshold:
    """Tests for non-retroactive period-spend threshold enforcement (T15)."""

    def test_no_period_threshold_passes_without_spend_history(self) -> None:
        rule = _make_rule(
            id=30,
            rule_key="dining.no_period_thresh",
            scope_type=ScopeType.CATEGORY,
            category="dining",
        )
        purchase = _make_purchase(category="dining", amount_cents=500)

        res = check_rule_applicability(rule, purchase, spend_history=None)

        assert res.is_applicable is True
        assert res.rejection_reason is None

    @pytest.mark.parametrize(
        ("prior_spend", "purchase_amount", "min_period_spend", "expected_applicable"),
        [
            # Below threshold
            (99999, 500, 100000, False),
            # Below threshold even though prior + current >= threshold (no retroactivity)
            (90000, 20000, 100000, False),
            # Exactly at threshold
            (100000, 500, 100000, True),
            # Above threshold
            (150000, 500, 100000, True),
        ],
    )
    def test_period_spend_threshold_boundaries_and_no_retroactivity(
        self,
        prior_spend: int,
        purchase_amount: int,
        min_period_spend: int,
        expected_applicable: bool,
    ) -> None:
        rule = _make_rule(
            id=31,
            rule_key="dining.unlocked_4x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_period_spend_cents=min_period_spend,
            threshold_period=Period.CALENDAR_YEAR,
        )
        purchase = _make_purchase(category="dining", amount_cents=purchase_amount)
        history = SpendHistory(threshold_spend_cents={"calendar_year": prior_spend})

        res = check_rule_applicability(rule, purchase, spend_history=history)

        assert res.is_applicable is expected_applicable
        if expected_applicable:
            assert res.rejection_reason is None
            assert res.rejection_detail is None
        else:
            assert res.rejection_reason == "below_min_period_spend"
            assert res.rejection_detail is not None
            assert str(prior_spend) in res.rejection_detail
            assert str(min_period_spend) in res.rejection_detail

    @pytest.mark.parametrize(
        ("period", "expected_key"),
        [
            (Period.MONTHLY, "monthly"),
            (Period.QUARTERLY, "quarterly"),
            (Period.CALENDAR_YEAR, "calendar_year"),
            (Period.CARD_YEAR, "card_year"),
        ],
    )
    def test_different_periods_use_period_specific_lookup_keys(
        self,
        period: Period,
        expected_key: str,
    ) -> None:
        rule = _make_rule(
            id=32,
            rule_key=f"dining.{expected_key}",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_period_spend_cents=50000,
            threshold_period=period,
        )
        purchase = _make_purchase(category="dining", amount_cents=1000)

        # Populate only the target period key above threshold; all other keys are 0
        history_match = SpendHistory(threshold_spend_cents={expected_key: 50000})
        assert check_rule_applicability(rule, purchase, spend_history=history_match).is_applicable

        # Populate a different period key; target period key defaults to 0 -> rejected
        other_key = "monthly" if expected_key != "monthly" else "quarterly"
        history_other = SpendHistory(threshold_spend_cents={other_key: 100000})
        res_other = check_rule_applicability(rule, purchase, spend_history=history_other)
        assert res_other.is_applicable is False
        assert res_other.rejection_reason == "below_min_period_spend"

    def test_two_rules_with_same_period_share_lookup(self) -> None:
        r_dining = _make_rule(
            id=33,
            rule_key="dining.tier2",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_period_spend_cents=50000,
            threshold_period=Period.QUARTERLY,
        )
        r_base = _make_rule(
            id=34,
            rule_key="base.tier2",
            scope_type=ScopeType.BASE,
            min_period_spend_cents=40000,
            threshold_period=Period.QUARTERLY,
        )
        purchase = _make_purchase(category="dining", amount_cents=1000)
        history = SpendHistory(threshold_spend_cents={"quarterly": 45000})

        applicable, traces = filter_applicable_rules(
            (r_dining, r_base), purchase, spend_history=history
        )

        assert applicable == (r_base,)
        assert len(traces) == 1
        assert traces[0].rule_id == 33
        assert traces[0].reason == "below_min_period_spend"

    def test_partial_threshold_configuration_raises_value_error(self) -> None:
        purchase = _make_purchase(category="dining")
        history = SpendHistory(threshold_spend_cents={"monthly": 50000})

        rule_no_period = _make_rule(
            id=35,
            rule_key="bad.no_period",
            scope_type=ScopeType.BASE,
            min_period_spend_cents=50000,
            threshold_period=None,
        )
        with pytest.raises(ValueError, match="threshold_period"):
            check_rule_applicability(rule_no_period, purchase, spend_history=history)

        rule_no_amount = _make_rule(
            id=36,
            rule_key="bad.no_amount",
            scope_type=ScopeType.BASE,
            min_period_spend_cents=None,
            threshold_period=Period.MONTHLY,
        )
        with pytest.raises(ValueError, match="min_period_spend_cents"):
            check_rule_applicability(rule_no_amount, purchase, spend_history=history)

    def test_threshold_configured_with_missing_spend_history_raises_value_error(self) -> None:
        rule = _make_rule(
            id=37,
            rule_key="dining.needs_history",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_period_spend_cents=50000,
            threshold_period=Period.CALENDAR_YEAR,
        )
        purchase = _make_purchase(category="dining")

        with pytest.raises(ValueError, match="spend_history"):
            check_rule_applicability(rule, purchase, spend_history=None)

    def test_rejected_period_threshold_rule_allows_fallback_rule_to_win(self) -> None:
        tier2_rule = _make_rule(
            id=201,
            rule_key="dining.tier2_5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            priority=10,
            min_period_spend_cents=100000,
            threshold_period=Period.CALENDAR_YEAR,
        )
        fallback_rule = _make_rule(
            id=202,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
            priority=0,
        )
        # Prior spend is $900; purchase is $200 (would reach $1,100, but no retroactivity)
        purchase = _make_purchase(category="dining", amount_cents=20000)
        history = SpendHistory(threshold_spend_cents={"calendar_year": 90000})

        applicable, traces = filter_applicable_rules(
            (tier2_rule, fallback_rule), purchase, spend_history=history
        )

        assert applicable == (fallback_rule,)
        assert len(traces) == 1
        assert traces[0].step_number == 1
        assert traces[0].step_type == "applicability_filter"
        assert traces[0].action == "rejected"
        assert traces[0].rule_id == 201
        assert traces[0].rule_key == "dining.tier2_5x"
        assert traces[0].reason == "below_min_period_spend"
        assert "$900.00" in traces[0].detail
        assert "$1000.00" in traces[0].detail

        selection = select_best_rule(applicable)
        assert selection is not None
        assert selection.winning_rule == fallback_rule

    def test_exact_minimum_threshold_passes(self) -> None:
        rule = _make_rule(
            id=22,
            rule_key="dining.min25",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=2500,
        )
        purchase = _make_purchase(category="dining", amount_cents=2500)

        res = check_rule_applicability(rule, purchase)

        assert res.is_applicable is True
        assert res.rejection_reason is None

    def test_above_minimum_threshold_passes(self) -> None:
        rule = _make_rule(
            id=23,
            rule_key="dining.min25",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=2500,
        )
        purchase = _make_purchase(category="dining", amount_cents=2501)

        res = check_rule_applicability(rule, purchase)

        assert res.is_applicable is True
        assert res.rejection_reason is None

    def test_scope_and_exclusion_precede_threshold_check(self) -> None:
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="fast_food",
            reason="Fast food excluded",
        )
        rule = _make_rule(
            id=24,
            rule_key="dining.min25.ex",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=2500,
            exclusions=(exclusion,),
        )

        # Scope mismatch takes precedence over threshold failure
        mismatch_res = check_rule_applicability(
            rule, _make_purchase(category="groceries", amount_cents=1000)
        )
        assert mismatch_res.is_applicable is False
        assert mismatch_res.rejection_reason == "category_mismatch"

        # Exclusion takes precedence over threshold failure
        excluded_res = check_rule_applicability(
            rule,
            _make_purchase(category="dining", merchant_tags=("fast_food",), amount_cents=1000),
        )
        assert excluded_res.is_applicable is False
        assert excluded_res.rejection_reason == "merchant_tag_exclusion"

    def test_ac7_threshold_rejection_allows_fallback_rule_to_win_selection(self) -> None:
        """AC-7: $25 min rule is rejected for $20 purchase; fallback rule wins via T11."""
        promo_rule = _make_rule(
            id=101,
            rule_key="dining.promo_5x",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier="5.0",
            priority=10,
            min_transaction_cents=2500,
        )
        fallback_rule = _make_rule(
            id=102,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
            priority=0,
            min_transaction_cents=None,
        )
        purchase = _make_purchase(category="dining", amount_cents=2000)

        applicable, rejection_traces = filter_applicable_rules(
            (promo_rule, fallback_rule), purchase
        )

        assert applicable == (fallback_rule,)
        assert len(rejection_traces) == 1
        trace = rejection_traces[0]
        assert trace.step_number == 1
        assert trace.step_type == "applicability_filter"
        assert trace.action == "rejected"
        assert trace.rule_id == 101
        assert trace.rule_key == "dining.promo_5x"
        assert trace.reason == "below_min_transaction"
        assert "2000" in trace.detail
        assert "2500" in trace.detail

        selection = select_best_rule(applicable)
        assert selection is not None
        assert selection.winning_rule == fallback_rule
        assert selection.alternative_rules == ()

    def test_multiple_rules_mixed_threshold_outcomes_deterministic_traces(self) -> None:
        r_high_min = _make_rule(
            id=1,
            rule_key="dining.min50",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=5000,
        )
        r_exact_min = _make_rule(
            id=2,
            rule_key="dining.min20",
            scope_type=ScopeType.CATEGORY,
            category="dining",
            min_transaction_cents=2000,
        )
        r_mid_min = _make_rule(
            id=3,
            rule_key="base.min30",
            scope_type=ScopeType.BASE,
            min_transaction_cents=3000,
        )
        r_no_min = _make_rule(
            id=4,
            rule_key="base.no_min",
            scope_type=ScopeType.BASE,
            min_transaction_cents=None,
        )
        purchase = _make_purchase(category="dining", amount_cents=2000)

        applicable, rejection_traces = filter_applicable_rules(
            (r_high_min, r_exact_min, r_mid_min, r_no_min), purchase
        )

        assert applicable == (r_exact_min, r_no_min)
        assert [t.step_number for t in rejection_traces] == [1, 2]
        assert [t.rule_id for t in rejection_traces] == [1, 3]
        assert [t.reason for t in rejection_traces] == [
            "below_min_transaction",
            "below_min_transaction",
        ]
