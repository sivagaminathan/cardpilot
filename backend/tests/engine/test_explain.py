"""Golden-text and unit tests for the trace explanation renderer (T19, FR-15, NFR-3).

Validates exact deterministic sentence rendering for happy-path, AC-5 cap
straddle, AC-4/AC-7/T15 applicability rejections, AC-2 no-valuation routing,
AC-6/no-applicable-rule ineligible outcomes, all cap_allocation variants,
unknown/empty trace steps, punctuation hygiene, input order preservation,
and immutability.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine.applicability import filter_applicable_rules
from app.engine.caps import allocate_purchase_across_caps
from app.engine.effective import create_no_effective_rule_evaluation
from app.engine.explain import render_explanation, render_trace_step
from app.engine.selection import create_no_applicable_rule_evaluation, select_best_rule
from app.engine.types import (
    CardContext,
    EarningRule,
    ExclusionType,
    Period,
    Purchase,
    RoundingMode,
    RuleExclusion,
    ScopeType,
    SpendCap,
    SpendHistory,
    TraceStep,
    Valuation,
)
from app.engine.units import calculate_reward_units
from app.engine.valuation import evaluate_valuation


def _make_rule(
    id: int,
    rule_key: str,
    scope_type: ScopeType,
    multiplier: str,
    category: str | None = None,
    merchant: str | None = None,
    cap_group_key: str | None = None,
    min_transaction_cents: int | None = None,
    min_period_spend_cents: int | None = None,
    threshold_period: Period | None = None,
    exclusions: tuple[RuleExclusion, ...] = (),
    rounding: RoundingMode = RoundingMode.FLOOR_UNITS,
    description: str = "",
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
        cap_group_key=cap_group_key,
        min_transaction_cents=min_transaction_cents,
        min_period_spend_cents=min_period_spend_cents,
        threshold_period=threshold_period,
        exclusions=exclusions,
        rounding=rounding,
        description=description,
    )


class TestGoldenTextExplanations:
    """Golden-text tests asserting exact tuple[str, ...] outputs."""

    def test_golden_happy_path(self) -> None:
        dining_rule = _make_rule(
            id=1,
            rule_key="dining.3x",
            scope_type=ScopeType.CATEGORY,
            multiplier="3.0",
            category="dining",
            description="Dining 3x",
        )
        purchase = Purchase(amount_cents=10000, category="dining", purchase_date=date(2026, 11, 15))
        selection = select_best_rule((dining_rule,))
        assert selection is not None
        cap_res = allocate_purchase_across_caps(purchase, (dining_rule,), (), SpendHistory())
        units_res = calculate_reward_units(cap_res.portions)
        val_res = evaluate_valuation(
            units_res.total_reward_units,
            "POINTS",
            Valuation("POINTS", Decimal("1.5"), is_user_set=True),
        )

        trace = (
            *selection.trace_steps,
            *cap_res.trace_steps,
            units_res.trace_step,
            val_res.trace_step,
        )
        rendered = render_explanation(trace)

        assert rendered == (
            "Selection: Selected rule 'dining.3x' 'Dining 3x' (v1, category, 3.0x, id=1) "
            "as highest-ranked applicable rule.",
            "Cap allocation: Allocated $100.00 (10000 cents) to uncapped rule 'dining.3x' (3.0x).",
            "Units: Calculated 1 portion(s) totaling 300.0 unrounded units; "
            "applied floor_units rounding -> 300 units (rule 'dining.3x').",
            "Valuation: Valued 300 POINTS units at 1.5 cents/unit -> 450 cents.",
        )

    def test_golden_ac5_cap_straddle_and_fallback(self) -> None:
        promo_rule = _make_rule(
            id=1,
            rule_key="dining.5x_q",
            scope_type=ScopeType.CATEGORY,
            multiplier="5.0",
            category="dining",
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
        purchase = Purchase(amount_cents=10000, category="dining", purchase_date=date(2026, 11, 15))

        selection = select_best_rule((promo_rule, base_rule))
        assert selection is not None
        cap_res = allocate_purchase_across_caps(purchase, (promo_rule, base_rule), (cap,), history)
        units_res = calculate_reward_units(cap_res.portions)
        val_res = evaluate_valuation(
            units_res.total_reward_units,
            "POINTS",
            Valuation("POINTS", Decimal("1.0"), is_user_set=True),
        )

        trace = (
            *selection.trace_steps,
            *cap_res.trace_steps,
            units_res.trace_step,
            val_res.trace_step,
        )
        rendered = render_explanation(trace)

        assert rendered == (
            "Selection: Selected rule 'dining.5x_q' (v1, category, 5.0x, id=1) "
            "as highest-ranked applicable rule.",
            "Selection: Not selected: rule 'base.1x' (v1, base, 1.0x, id=2) has lower scope "
            "specificity (base) than winning rule 'dining.5x_q' (v1, category, 5.0x, id=1).",
            "Cap allocation: Allocated $50.00 (5000 cents) to rule 'dining.5x_q' (5.0x) "
            "under cap group 'dining_q' (remaining before purchase: $50.00 (5000 cents)).",
            "Cap allocation: Allocated $50.00 (5000 cents) to uncapped rule 'base.1x' (1.0x).",
            "Units: Calculated 2 portion(s) totaling 300.0 unrounded units; "
            "applied floor_units rounding -> 300 units (rule 'dining.5x_q').",
            "Valuation: Valued 300 POINTS units at 1.0 cents/unit -> 300 cents.",
        )

    def test_golden_applicability_exclusions_and_thresholds_with_fallback(self) -> None:
        excluded_rule = _make_rule(
            id=1,
            rule_key="grocery.4x",
            scope_type=ScopeType.CATEGORY,
            multiplier="4.0",
            category="groceries",
            exclusions=(
                RuleExclusion(
                    exclusion_type=ExclusionType.MERCHANT_TAG,
                    target="warehouse_club",
                    reason="Warehouse clubs excluded",
                ),
            ),
        )
        min_tx_rule = _make_rule(
            id=2,
            rule_key="grocery.min25",
            scope_type=ScopeType.CATEGORY,
            multiplier="3.0",
            category="groceries",
            min_transaction_cents=2500,
        )
        period_rule = _make_rule(
            id=3,
            rule_key="grocery.tier2",
            scope_type=ScopeType.CATEGORY,
            multiplier="3.5",
            category="groceries",
            min_period_spend_cents=100000,
            threshold_period=Period.CALENDAR_YEAR,
        )
        base_rule = _make_rule(
            id=4,
            rule_key="base.1x",
            scope_type=ScopeType.BASE,
            multiplier="1.0",
        )
        purchase = Purchase(
            amount_cents=2000,
            category="groceries",
            purchase_date=date(2026, 11, 15),
            merchant="Bulk Mart",
            merchant_tags=("warehouse_club",),
        )
        history = SpendHistory(threshold_spend_cents={"calendar_year": 50000})

        applicable, app_traces = filter_applicable_rules(
            (excluded_rule, min_tx_rule, period_rule, base_rule), purchase, spend_history=history
        )
        selection = select_best_rule(applicable)
        assert selection is not None
        cap_res = allocate_purchase_across_caps(purchase, applicable, (), history)
        units_res = calculate_reward_units(cap_res.portions)
        val_res = evaluate_valuation(
            units_res.total_reward_units,
            "CASH_USD",
            Valuation("CASH_USD", Decimal("1.0"), is_user_set=False),
        )

        trace = (
            *app_traces,
            *selection.trace_steps,
            *cap_res.trace_steps,
            units_res.trace_step,
            val_res.trace_step,
        )
        rendered = render_explanation(trace)

        assert rendered == (
            "Applicability: Purchase merchant tag 'warehouse_club' is excluded: "
            "Warehouse clubs excluded (rule 'grocery.4x').",
            "Applicability: Purchase amount $20.00 (2000 cents) is below rule minimum "
            "transaction threshold of $25.00 (2500 cents) (rule 'grocery.min25').",
            "Applicability: Prior calendar_year spend $500.00 (50000 cents) is below rule "
            "period-spend threshold of $1000.00 (100000 cents) (rule 'grocery.tier2').",
            "Selection: Selected rule 'base.1x' (v1, base, 1.0x, id=4) "
            "as highest-ranked applicable rule.",
            "Cap allocation: Allocated $20.00 (2000 cents) to uncapped rule 'base.1x' (1.0x).",
            "Units: Calculated 1 portion(s) totaling 20.0 unrounded units; "
            "applied floor_units rounding -> 20 units (rule 'base.1x').",
            "Valuation: Valued 20 CASH_USD units at 1.0 cents/unit -> 20 cents.",
        )

    def test_golden_cap_exhausted_and_no_fallback_unallocated(self) -> None:
        capped_rule = _make_rule(
            id=1,
            rule_key="dining.5x",
            scope_type=ScopeType.CATEGORY,
            multiplier="5.0",
            category="dining",
            cap_group_key="dining_q",
        )
        partial_rule = _make_rule(
            id=2,
            rule_key="dining.2x",
            scope_type=ScopeType.CATEGORY,
            multiplier="2.0",
            category="dining",
            cap_group_key="dining_m",
        )
        caps = (
            SpendCap(cap_group_key="dining_q", cap_amount_cents=50000, period=Period.QUARTERLY),
            SpendCap(cap_group_key="dining_m", cap_amount_cents=10000, period=Period.MONTHLY),
        )
        history = SpendHistory(cap_spend_cents={"dining_q": 50000, "dining_m": 8000})
        purchase = Purchase(amount_cents=5000, category="dining", purchase_date=date(2026, 11, 15))

        cap_res = allocate_purchase_across_caps(
            purchase, (capped_rule, partial_rule), caps, history
        )
        rendered = render_explanation(cap_res.trace_steps)

        assert rendered == (
            "Cap allocation: Cap group 'dining_q' for rule 'dining.5x' is exhausted "
            "(cap $500.00 (50000 cents), prior spend $500.00 (50000 cents)).",
            "Cap allocation: Allocated $20.00 (2000 cents) to rule 'dining.2x' (2.0x) "
            "under cap group 'dining_m' (remaining before purchase: $20.00 (2000 cents)).",
            "Cap allocation: No eligible fallback rule remains for unallocated amount "
            "$30.00 (3000 cents).",
        )

    def test_golden_ac2_no_valuation_routing(self) -> None:
        rule = _make_rule(1, "miles.2x", ScopeType.BASE, multiplier="2.0")
        purchase = Purchase(amount_cents=5000, category="travel", purchase_date=date(2026, 11, 15))
        selection = select_best_rule((rule,))
        assert selection is not None
        cap_res = allocate_purchase_across_caps(purchase, (rule,), (), SpendHistory())
        units_res = calculate_reward_units(cap_res.portions)
        val_res = evaluate_valuation(units_res.total_reward_units, "Skyward Miles", None)

        rendered = render_explanation(
            (*selection.trace_steps, units_res.trace_step, val_res.trace_step)
        )

        assert rendered == (
            "Selection: Selected rule 'miles.2x' (v1, base, 2.0x, id=1) "
            "as highest-ranked applicable rule.",
            "Units: Calculated 1 portion(s) totaling 100.0 unrounded units; "
            "applied floor_units rounding -> 100 units (rule 'miles.2x').",
            "Valuation: Cannot value 100 Skyward Miles units: No estimated value is set for "
            "Skyward Miles, so this card cannot be reliably compared in dollars. "
            "Set a valuation in Settings.",
        )

    def test_golden_ineligible_outcomes(self) -> None:
        card = CardContext(card_id=1, card_name="Traveler", reward_currency="MILES", rules=())
        purchase = Purchase(amount_cents=2500, category="dining", purchase_date=date(2026, 11, 15))

        no_eff = create_no_effective_rule_evaluation(card, purchase.purchase_date)
        no_app = create_no_applicable_rule_evaluation(card, purchase)

        assert render_explanation(no_eff.trace) == (
            "Effective check: No earning rules for 'Traveler' are effective on 2026-11-15.",
        )
        assert render_explanation(no_app.trace) == (
            "Selection: No earning rules for 'Traveler' apply to category 'dining' on 2026-11-15.",
        )


class TestEdgeCasesOrderingAndImmutability:
    """Tests for empty traces, unknown steps, punctuation hygiene, ordering, and determinism."""

    def test_empty_trace_returns_empty_tuple(self) -> None:
        assert render_explanation(()) == ()

    def test_unknown_step_type_and_empty_detail_fallback(self) -> None:
        with_detail = TraceStep(
            step_number=1,
            step_type="custom_audit",
            action="checked",
            detail="  Verified custom rule invariant..  ",
        )
        without_detail = TraceStep(
            step_number=2,
            step_type="custom_audit",
            action="flagged",
            detail="   ",
            rule_key="custom.1x",
            reason="audit_flag",
        )

        assert render_trace_step(with_detail) == "Verified custom rule invariant."
        assert (
            render_trace_step(without_detail)
            == "Step custom_audit (flagged) for rule 'custom.1x' (audit_flag)."
        )

    def test_preserves_caller_sequence_order_even_with_duplicate_step_numbers(self) -> None:
        s1 = TraceStep(step_number=1, step_type="valuation", action="valued", detail="Second step.")
        s2 = TraceStep(
            step_number=1, step_type="selection", action="selected", detail="First step."
        )

        assert render_explanation((s1, s2)) == (
            "Valuation: Second step.",
            "Selection: First step.",
        )

    def test_sentence_hygiene_no_double_periods_and_always_ends_with_period(self) -> None:
        steps = (
            TraceStep(1, "selection", "selected", "  Selected rule.. "),
            TraceStep(1, "valuation", "valued", "Valued 10 units"),
            TraceStep(1, "unknown_step", "noop", "   "),
        )
        rendered = render_explanation(steps)

        assert len(rendered) == 3
        for sentence in rendered:
            assert sentence != ""
            assert sentence == sentence.strip()
            assert sentence.endswith(".")
            assert not sentence.endswith("..")

    def test_set_rejection_list_normalization_and_determinism(self) -> None:
        step = TraceStep(1, "selection", "selected", "Selected base rule.")

        with pytest.raises(TypeError, match="set"):
            render_explanation({step})  # type: ignore[arg-type]

        r1 = render_explanation([step])
        r2 = render_explanation((step,))
        assert isinstance(r1, tuple)
        assert r1 == r2
