"""Unit tests for deterministic rule selection (T11, AC-3, AC-13).

Validates specificity ordering (MERCHANT > CATEGORY > BASE), priority descending,
rule ID ascending tie-breaking, duplicate ID rejection, AC-13 determinism across
shuffled inputs, selection trace/explanation details, and no-applicable-rule
ineligible evaluation.
"""

import random
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from app.engine.selection import (
    SelectionResult,
    create_no_applicable_rule_evaluation,
    select_best_rule,
    sort_rules_by_selection_priority,
)
from app.engine.types import (
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    IneligibleReason,
    Purchase,
    ScopeType,
    TraceStep,
)


def _make_rule(
    rule_id: int,
    rule_key: str,
    scope_type: ScopeType,
    priority: int = 0,
    multiplier: str = "1.0",
    description: str = "",
) -> EarningRule:
    """Helper to construct an EarningRule for selection testing."""
    return EarningRule(
        id=rule_id,
        rule_key=rule_key,
        version=1,
        scope_type=scope_type,
        multiplier=Decimal(multiplier),
        effective_from=date(2026, 1, 1),
        priority=priority,
        description=description,
    )


def _make_purchase(category: str = "dining", merchant: str | None = "Acme Bistro") -> Purchase:
    """Helper to construct a Purchase for selection testing."""
    return Purchase(
        amount_cents=10000,
        category=category,
        purchase_date=date(2026, 11, 15),
        merchant=merchant,
    )


class TestSortRulesBySelectionPriority:
    """Tests for deterministic sorting: specificity -> priority -> id."""

    def test_specificity_order_merchant_category_base(self) -> None:
        base_rule = _make_rule(1, "base.1x", ScopeType.BASE, priority=100, multiplier="1.0")
        cat_rule = _make_rule(2, "dining.3x", ScopeType.CATEGORY, priority=50, multiplier="3.0")
        merch_rule = _make_rule(3, "bistro.5x", ScopeType.MERCHANT, priority=0, multiplier="5.0")

        ordered = sort_rules_by_selection_priority([base_rule, cat_rule, merch_rule])
        assert ordered == (merch_rule, cat_rule, base_rule)

    def test_priority_descending_including_negative_zero_positive(self) -> None:
        r_neg = _make_rule(1, "cat.neg", ScopeType.CATEGORY, priority=-5)
        r_zero = _make_rule(2, "cat.zero", ScopeType.CATEGORY, priority=0)
        r_pos = _make_rule(3, "cat.pos", ScopeType.CATEGORY, priority=10)

        ordered = sort_rules_by_selection_priority([r_neg, r_zero, r_pos])
        assert ordered == (r_pos, r_zero, r_neg)

    def test_rule_id_ascending_tie_break(self) -> None:
        r_high_id = _make_rule(30, "cat.thirty", ScopeType.CATEGORY, priority=5)
        r_low_id = _make_rule(10, "cat.ten", ScopeType.CATEGORY, priority=5)
        r_mid_id = _make_rule(20, "cat.twenty", ScopeType.CATEGORY, priority=5)

        ordered = sort_rules_by_selection_priority([r_high_id, r_low_id, r_mid_id])
        assert ordered == (r_low_id, r_mid_id, r_high_id)

    def test_determinism_across_shuffled_inputs_ac13(self) -> None:
        rules = [
            _make_rule(1, "base.1", ScopeType.BASE, priority=0),
            _make_rule(2, "base.2", ScopeType.BASE, priority=10),
            _make_rule(3, "cat.1", ScopeType.CATEGORY, priority=0),
            _make_rule(4, "cat.2", ScopeType.CATEGORY, priority=0),
            _make_rule(5, "merch.1", ScopeType.MERCHANT, priority=-1),
        ]
        expected = sort_rules_by_selection_priority(rules)

        rng = random.Random(42)
        for _ in range(10):
            shuffled = list(rules)
            rng.shuffle(shuffled)
            assert sort_rules_by_selection_priority(shuffled) == expected

    def test_duplicate_rule_ids_rejected(self) -> None:
        r1 = _make_rule(10, "rule.a", ScopeType.CATEGORY, priority=5)
        r2 = _make_rule(10, "rule.b", ScopeType.CATEGORY, priority=5)

        with pytest.raises(ValueError, match="Duplicate rule id 10"):
            sort_rules_by_selection_priority([r1, r2])


class TestSelectBestRule:
    """Tests for select_best_rule winner, alternatives, trace, and explanation."""

    def test_empty_input_returns_none(self) -> None:
        assert select_best_rule([]) is None
        assert select_best_rule(()) is None

    def test_ac3_specificity_selection_and_explanation(self) -> None:
        base_rule = _make_rule(
            1,
            "card.base",
            ScopeType.BASE,
            multiplier="1.0",
            description="Base 1x",
        )
        dining_rule = _make_rule(
            2,
            "card.dining",
            ScopeType.CATEGORY,
            multiplier="3.0",
            description="Dining 3x",
        )
        merchant_rule = _make_rule(
            3,
            "card.bistro",
            ScopeType.MERCHANT,
            multiplier="5.0",
            description="Bistro 5x",
        )

        result = select_best_rule([base_rule, dining_rule, merchant_rule])
        assert isinstance(result, SelectionResult)
        assert result.winning_rule == merchant_rule
        assert result.alternative_rules == (dining_rule, base_rule)

        # Trace steps: 1 winner + 2 alternatives
        assert len(result.trace_steps) == 3
        win_step, alt1_step, alt2_step = result.trace_steps

        assert win_step.step_number == 1
        assert win_step.step_type == "selection"
        assert win_step.action == "selected"
        assert win_step.rule_id == 3
        assert win_step.rule_key == "card.bistro"
        assert win_step.reason is None

        assert alt1_step.step_number == 2
        assert alt1_step.step_type == "selection"
        assert alt1_step.action == "not_selected"
        assert alt1_step.rule_id == 2
        assert alt1_step.rule_key == "card.dining"
        assert alt1_step.reason == "lower_specificity"
        assert "ineligible" not in alt1_step.detail.lower()

        assert alt2_step.step_number == 3
        assert alt2_step.step_type == "selection"
        assert alt2_step.action == "not_selected"
        assert alt2_step.rule_id == 1
        assert alt2_step.rule_key == "card.base"
        assert alt2_step.reason == "lower_specificity"

        # Explanation names winner and alternatives
        assert "card.bistro" in result.explanation
        assert "Bistro 5x" in result.explanation
        assert "card.dining" in result.explanation
        assert "card.base" in result.explanation

    def test_tie_break_reasons_in_trace(self) -> None:
        winner = _make_rule(10, "cat.winner", ScopeType.CATEGORY, priority=10, multiplier="3.0")
        lost_priority = _make_rule(
            5, "cat.low_prio", ScopeType.CATEGORY, priority=5, multiplier="3.0"
        )
        lost_id = _make_rule(20, "cat.high_id", ScopeType.CATEGORY, priority=10, multiplier="3.0")
        lost_spec = _make_rule(1, "base.low_spec", ScopeType.BASE, priority=99, multiplier="1.0")

        result = select_best_rule([lost_spec, lost_id, lost_priority, winner])
        assert result is not None
        assert result.winning_rule == winner
        assert result.alternative_rules == (lost_id, lost_priority, lost_spec)

        alt_steps = result.trace_steps[1:]
        assert alt_steps[0].rule_id == 20
        assert alt_steps[0].reason == "rule_id_tie_break"

        assert alt_steps[1].rule_id == 5
        assert alt_steps[1].reason == "lower_priority"

        assert alt_steps[2].rule_id == 1
        assert alt_steps[2].reason == "lower_specificity"

    def test_single_rule_no_alternatives(self) -> None:
        only_rule = _make_rule(1, "base.only", ScopeType.BASE, multiplier="1.5")
        result = select_best_rule([only_rule])

        assert result is not None
        assert result.winning_rule == only_rule
        assert result.alternative_rules == ()
        assert len(result.trace_steps) == 1
        assert result.trace_steps[0].action == "selected"
        assert "base.only" in result.explanation

    def test_combined_all_three_specificities_and_priorities(self) -> None:
        """Combined 5-rule scenario spanning MERCHANT, CATEGORY, BASE and multiple priorities."""
        m_win = _make_rule(10, "merch.win", ScopeType.MERCHANT, priority=5, multiplier="5.0")
        m_tie = _make_rule(20, "merch.tie_id", ScopeType.MERCHANT, priority=5, multiplier="5.0")
        m_low = _make_rule(5, "merch.low_p", ScopeType.MERCHANT, priority=1, multiplier="4.0")
        cat_high = _make_rule(3, "cat.high_p", ScopeType.CATEGORY, priority=50, multiplier="3.0")
        base_top = _make_rule(1, "base.top_p", ScopeType.BASE, priority=100, multiplier="1.5")

        result = select_best_rule([base_top, m_low, cat_high, m_tie, m_win])
        assert result is not None

        assert result.winning_rule == m_win
        assert result.alternative_rules == (m_tie, m_low, cat_high, base_top)

        assert len(result.trace_steps) == 5
        assert result.trace_steps[0].rule_id == 10
        assert result.trace_steps[0].action == "selected"

        assert result.trace_steps[1].rule_id == 20
        assert result.trace_steps[1].reason == "rule_id_tie_break"

        assert result.trace_steps[2].rule_id == 5
        assert result.trace_steps[2].reason == "lower_priority"

        assert result.trace_steps[3].rule_id == 3
        assert result.trace_steps[3].reason == "lower_specificity"

        assert result.trace_steps[4].rule_id == 1
        assert result.trace_steps[4].reason == "lower_specificity"

        for key in ("merch.win", "merch.tie_id", "merch.low_p", "cat.high_p", "base.top_p"):
            assert key in result.explanation


class TestSelectionResultImmutability:
    """Tests for runtime immutability and sequence determinism of SelectionResult."""

    def test_direct_construction_normalizes_lists_to_tuples(self) -> None:
        win = _make_rule(1, "win", ScopeType.MERCHANT)
        alt = _make_rule(2, "alt", ScopeType.BASE)
        step = TraceStep(step_number=1, step_type="selection", action="selected", detail="ok")

        alts_list = [alt]
        steps_list = [step]

        res = SelectionResult(
            winning_rule=win,
            alternative_rules=alts_list,  # type: ignore[arg-type]
            trace_steps=steps_list,  # type: ignore[arg-type]
            explanation="Selected win",
        )

        assert isinstance(res.alternative_rules, tuple)
        assert isinstance(res.trace_steps, tuple)

        # Mutating caller lists does not affect SelectionResult
        alts_list.clear()
        steps_list.clear()
        assert len(res.alternative_rules) == 1
        assert len(res.trace_steps) == 1

        # Mutating fields or tuple attributes fails
        with pytest.raises(FrozenInstanceError):
            res.explanation = "changed"  # type: ignore[misc]

        with pytest.raises((TypeError, AttributeError)):
            res.alternative_rules[0] = win  # type: ignore[index]

    def test_rejects_unordered_sets(self) -> None:
        win = _make_rule(1, "win", ScopeType.MERCHANT)
        alt = _make_rule(2, "alt", ScopeType.BASE)
        step = TraceStep(step_number=1, step_type="selection", action="selected", detail="ok")

        with pytest.raises(TypeError, match="must be an ordered sequence"):
            SelectionResult(
                winning_rule=win,
                alternative_rules={alt},  # type: ignore[arg-type]
                trace_steps=(step,),
                explanation="Selected win",
            )

        with pytest.raises(TypeError, match="must be an ordered sequence"):
            SelectionResult(
                winning_rule=win,
                alternative_rules=(alt,),
                trace_steps=frozenset([step]),  # type: ignore[arg-type]
                explanation="Selected win",
            )


class TestNoApplicableRuleEvaluation:
    """Tests for create_no_applicable_rule_evaluation."""

    def test_creates_ineligible_evaluation(self) -> None:
        card = CardContext(
            card_id=7,
            card_name="Category Specialist Card",
            reward_currency="CS_PTS",
            rules=(),
        )
        purchase = _make_purchase(category="utilities", merchant="City Power")

        evaluation = create_no_applicable_rule_evaluation(card, purchase)

        assert isinstance(evaluation, CardEvaluation)
        assert evaluation.card_id == 7
        assert evaluation.card_name == "Category Specialist Card"
        assert evaluation.reward_currency == "CS_PTS"
        assert evaluation.status == CardStatus.INELIGIBLE
        assert evaluation.reward_units == Decimal("0")
        assert evaluation.estimated_value_cents is None
        assert evaluation.valuation_used is None
        assert evaluation.applied_portions == ()
        assert evaluation.rejection_reason == IneligibleReason.NO_APPLICABLE_RULE.value
        assert evaluation.rejection_message is not None
        assert "utilities" in evaluation.rejection_message
        assert len(evaluation.explanation) == 1
        assert len(evaluation.trace) == 1
        assert evaluation.trace[0].step_type == "selection"
        assert evaluation.trace[0].action == "rejected"
        assert evaluation.trace[0].reason == IneligibleReason.NO_APPLICABLE_RULE.value

    def test_custom_message_trimmed_and_empty_falls_back_to_default(self) -> None:
        card = CardContext(
            card_id=8,
            card_name="Travel Card",
            reward_currency="TRV_MI",
            rules=(),
        )
        purchase = _make_purchase(category="groceries")

        # Valid custom message is trimmed
        eval_custom = create_no_applicable_rule_evaluation(
            card, purchase, message="  No matching category or base rule.  "
        )
        assert eval_custom.rejection_message == "No matching category or base rule."
        assert eval_custom.explanation == ("No matching category or base rule.",)

        # Empty and whitespace messages fall back to default
        eval_empty = create_no_applicable_rule_evaluation(card, purchase, message="")
        eval_ws = create_no_applicable_rule_evaluation(card, purchase, message="   ")

        assert eval_empty.rejection_message is not None
        assert "Travel Card" in eval_empty.rejection_message
        assert "groceries" in eval_empty.rejection_message
        assert eval_ws.rejection_message == eval_empty.rejection_message
