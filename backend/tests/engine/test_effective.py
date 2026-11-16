"""Unit tests for the reward engine effective-date filter (T09, AC-6).

Validates inclusive boundary matching, open-ended rules, AC-6 rule version transitions,
order preservation, and ineligible evaluation creation when no rules are effective.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.engine.effective import (
    create_no_effective_rule_evaluation,
    filter_effective_rules,
    is_rule_effective,
)
from app.engine.types import (
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    IneligibleReason,
    ScopeType,
)


def _make_rule(
    id: int,
    rule_key: str,
    version: int,
    effective_from: date,
    effective_to: date | None = None,
    multiplier: str = "1.0",
) -> EarningRule:
    """Helper to create a minimal EarningRule for effective-date testing."""
    return EarningRule(
        id=id,
        rule_key=rule_key,
        version=version,
        scope_type=ScopeType.BASE,
        multiplier=Decimal(multiplier),
        effective_from=effective_from,
        effective_to=effective_to,
    )


class TestIsRuleEffective:
    """Tests for inclusive boundary date semantics."""

    def test_inclusive_boundaries_bounded_rule(self) -> None:
        start = date(2026, 3, 1)
        end = date(2026, 3, 31)
        rule = _make_rule(1, "promo", 1, start, end)

        # 1. Exactly on effective_from -> True
        assert is_rule_effective(rule, start) is True

        # 2. One day before effective_from -> False
        assert is_rule_effective(rule, start - timedelta(days=1)) is False

        # 3. Within effective range -> True
        assert is_rule_effective(rule, date(2026, 3, 15)) is True

        # 4. Exactly on effective_to -> True
        assert is_rule_effective(rule, end) is True

        # 5. One day after effective_to -> False
        assert is_rule_effective(rule, end + timedelta(days=1)) is False

    def test_open_ended_effective_to(self) -> None:
        start = date(2026, 1, 1)
        rule = _make_rule(1, "base.standard", 1, start, effective_to=None)

        # Before start -> False
        assert is_rule_effective(rule, date(2025, 12, 31)) is False

        # On start -> True
        assert is_rule_effective(rule, start) is True

        # Far into the future -> True
        assert is_rule_effective(rule, date(2035, 12, 31)) is True
        assert is_rule_effective(rule, date(2099, 1, 1)) is True

    def test_single_day_effective_rule(self) -> None:
        single_day = date(2026, 7, 4)
        rule = _make_rule(1, "holiday.special", 1, single_day, single_day)

        assert is_rule_effective(rule, single_day - timedelta(days=1)) is False
        assert is_rule_effective(rule, single_day) is True
        assert is_rule_effective(rule, single_day + timedelta(days=1)) is False


class TestAC6VersionTransition:
    """SPEC AC-6: v1 effective through 2026-06-30 and v2 from 2026-07-01."""

    def test_ac6_version_selection(self) -> None:
        v1 = _make_rule(10, "dining", 1, date(2026, 1, 1), date(2026, 6, 30), multiplier="3.0")
        v2 = _make_rule(11, "dining", 2, date(2026, 7, 1), None, multiplier="4.0")
        rules = (v1, v2)

        # On 2026-06-30: v1 is effective, v2 is not
        eff_june = filter_effective_rules(rules, date(2026, 6, 30))
        assert eff_june == (v1,)

        # On 2026-07-01: v2 is effective, v1 is not
        eff_july = filter_effective_rules(rules, date(2026, 7, 1))
        assert eff_july == (v2,)


class TestFilterEffectiveRules:
    """Tests for multi-rule filtering and input order preservation."""

    def test_preserves_input_order(self) -> None:
        target = date(2026, 5, 15)
        # 3 effective rules interspersed with an expired and a future rule
        r1 = _make_rule(1, "merchant.first", 1, date(2026, 1, 1), date(2026, 12, 31))
        r_expired = _make_rule(2, "expired", 1, date(2026, 1, 1), date(2026, 4, 30))
        r2 = _make_rule(3, "category.second", 1, date(2026, 5, 1), None)
        r_future = _make_rule(4, "future", 1, date(2026, 6, 1), None)
        r3 = _make_rule(5, "base.third", 1, date(2025, 1, 1), None)

        filtered = filter_effective_rules(
            [r1, r_expired, r2, r_future, r3],
            target,
        )
        assert filtered == (r1, r2, r3)
        assert [r.id for r in filtered] == [1, 3, 5]

    def test_returns_empty_tuple_when_none_effective(self) -> None:
        target = date(2026, 1, 1)
        future_rule = _make_rule(1, "future", 1, date(2026, 6, 1), None)
        assert filter_effective_rules([future_rule], target) == ()
        assert filter_effective_rules([], target) == ()


class TestNoEffectiveRuleEvaluation:
    """Tests for AC-6 ineligible evaluation when no rules are effective."""

    def test_creates_ineligible_evaluation(self) -> None:
        target = date(2026, 1, 1)
        future_rule = _make_rule(1, "dining", 1, date(2026, 6, 1), None)
        card = CardContext(
            card_id=42,
            card_name="Horizon Points Card",
            reward_currency="HZ_PTS",
            rules=(future_rule,),
        )

        evaluation = create_no_effective_rule_evaluation(card, target)

        assert isinstance(evaluation, CardEvaluation)
        assert evaluation.card_id == 42
        assert evaluation.card_name == "Horizon Points Card"
        assert evaluation.reward_currency == "HZ_PTS"
        assert evaluation.status == CardStatus.INELIGIBLE
        assert evaluation.reward_units == Decimal("0")
        assert evaluation.estimated_value_cents is None
        assert evaluation.valuation_used is None
        assert evaluation.applied_portions == ()
        assert evaluation.rejection_reason == IneligibleReason.NO_EFFECTIVE_RULE.value
        assert "effective" in evaluation.rejection_message.lower()  # type: ignore[union-attr]
        assert len(evaluation.explanation) == 1
        assert len(evaluation.trace) == 1
        assert evaluation.trace[0].step_type == "effective_filter"
        assert evaluation.trace[0].action == "rejected"
        assert evaluation.trace[0].reason == IneligibleReason.NO_EFFECTIVE_RULE.value

    def test_custom_message_supported(self) -> None:
        target = date(2026, 1, 1)
        card = CardContext(
            card_id=1,
            card_name="Empty Card",
            reward_currency="USD",
            rules=(),
        )
        custom_msg = "  Card has no active terms on 2026-01-01.  "
        expected_msg = "Card has no active terms on 2026-01-01."
        evaluation = create_no_effective_rule_evaluation(card, target, message=custom_msg)

        assert evaluation.rejection_message == expected_msg
        assert evaluation.explanation == (expected_msg,)
        assert evaluation.trace[0].detail == expected_msg

    def test_empty_or_whitespace_message_uses_default(self) -> None:
        target = date(2026, 1, 1)
        card = CardContext(
            card_id=1,
            card_name="Empty Card",
            reward_currency="USD",
            rules=(),
        )
        expected_default = "No earning rules for 'Empty Card' are effective on 2026-01-01."

        # 1. Empty string message=""
        eval_empty = create_no_effective_rule_evaluation(card, target, message="")
        assert eval_empty.rejection_message == expected_default
        assert eval_empty.explanation == (expected_default,)
        assert eval_empty.trace[0].detail == expected_default

        # 2. Whitespace-only message="   "
        eval_ws = create_no_effective_rule_evaluation(card, target, message="   ")
        assert eval_ws.rejection_message == expected_default
        assert eval_ws.explanation == (expected_default,)
        assert eval_ws.trace[0].detail == expected_default
