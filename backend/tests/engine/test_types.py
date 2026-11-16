"""Unit tests for pure reward engine domain types (T08).

Validates construction, deep immutability, runtime type constraints, collection determinism,
finiteness, and boundary conditions.
"""

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from app.engine.types import (
    AppliedPortion,
    Cap,
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    ExclusionType,
    IneligibleReason,
    Period,
    PostCapBehavior,
    Purchase,
    RoundingMode,
    Rule,
    RuleExclusion,
    ScopeType,
    SpendCap,
    SpendHistory,
    TraceStep,
    UnrankedReason,
    Valuation,
)


class TestPurchase:
    """Tests for Purchase dataclass."""

    def test_construction_and_accessors(self) -> None:
        purchase = Purchase(
            amount_cents=5000,
            category="dining",
            purchase_date=date(2026, 11, 15),
            merchant="Acme Bistro",
            merchant_tags=("sit_down",),
        )
        assert purchase.amount_cents == 5000
        assert purchase.category == "dining"
        assert purchase.purchase_date == date(2026, 11, 15)
        assert purchase.merchant == "Acme Bistro"
        assert purchase.merchant_tags == ("sit_down",)

    def test_immutability(self) -> None:
        purchase = Purchase(
            amount_cents=2500,
            category="groceries",
            purchase_date=date(2026, 11, 15),
        )
        with pytest.raises(FrozenInstanceError):
            purchase.amount_cents = 3000  # type: ignore[misc]

    def test_deep_immutability_of_merchant_tags(self) -> None:
        tags_list = ["warehouse_club", "big_box"]
        purchase = Purchase(
            amount_cents=2500,
            category="groceries",
            purchase_date=date(2026, 11, 15),
            merchant_tags=tags_list,
        )
        assert isinstance(purchase.merchant_tags, tuple)
        # Mutating original list should not affect purchase.merchant_tags
        tags_list.append("grocery_store")
        assert purchase.merchant_tags == ("warehouse_club", "big_box")

    def test_rejects_unordered_set_for_tags(self) -> None:
        with pytest.raises(TypeError, match="must be an ordered sequence"):
            Purchase(
                amount_cents=2500,
                category="groceries",
                purchase_date=date(2026, 11, 15),
                merchant_tags={"tag1", "tag2"},  # type: ignore[arg-type]
            )

        with pytest.raises(TypeError, match="must be an ordered sequence"):
            Purchase(
                amount_cents=2500,
                category="groceries",
                purchase_date=date(2026, 11, 15),
                merchant_tags=frozenset(["tag1"]),  # type: ignore[arg-type]
            )

    def test_numeric_validation(self) -> None:
        # Strictly positive integer required
        with pytest.raises(ValueError, match="strictly positive"):
            Purchase(amount_cents=0, category="dining", purchase_date=date(2026, 11, 15))

        with pytest.raises(ValueError, match="strictly positive"):
            Purchase(amount_cents=-500, category="dining", purchase_date=date(2026, 11, 15))

        # Rejects float
        with pytest.raises(TypeError, match="amount_cents must be an integer"):
            Purchase(amount_cents=10.5, category="dining", purchase_date=date(2026, 11, 15))  # type: ignore[arg-type]

        # Rejects bool
        with pytest.raises(TypeError, match="amount_cents must be an integer"):
            Purchase(amount_cents=True, category="dining", purchase_date=date(2026, 11, 15))  # type: ignore[arg-type]


class TestEarningRule:
    """Tests for EarningRule dataclass and Rule alias."""

    def test_construction_and_aliases(self) -> None:
        assert Rule is EarningRule
        exclusion = RuleExclusion(
            exclusion_type=ExclusionType.MERCHANT_TAG,
            target="warehouse_club",
            reason="Warehouse clubs excluded from grocery bonus",
        )
        rule = EarningRule(
            id=1,
            rule_key="nwcash.dining",
            version=1,
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier=Decimal("3.0"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            rounding=RoundingMode.FLOOR_UNITS,
            priority=10,
            post_cap_behavior=PostCapBehavior.FALLBACK_TO_BASE,
            exclusions=(exclusion,),
        )
        assert rule.id == 1
        assert rule.rule_key == "nwcash.dining"
        assert rule.multiplier == Decimal("3.0")
        assert rule.scope_type == ScopeType.CATEGORY
        assert rule.effective_to == date(2026, 12, 31)
        assert rule.post_cap_behavior == PostCapBehavior.FALLBACK_TO_BASE
        assert len(rule.exclusions) == 1
        assert rule.exclusions[0].exclusion_type == ExclusionType.MERCHANT_TAG

    def test_immutability(self) -> None:
        rule = EarningRule(
            id=1,
            rule_key="nwcash.base",
            version=1,
            scope_type=ScopeType.BASE,
            multiplier=Decimal("1.0"),
            effective_from=date(2026, 1, 1),
        )
        with pytest.raises(FrozenInstanceError):
            rule.multiplier = Decimal("2.0")  # type: ignore[misc]

    def test_deep_immutability_of_exclusions(self) -> None:
        ex = RuleExclusion(
            exclusion_type=ExclusionType.CATEGORY,
            target="utilities",
            reason="Not eligible",
        )
        exclusions_list = [ex]
        rule = EarningRule(
            id=1,
            rule_key="nwcash.base",
            version=1,
            scope_type=ScopeType.BASE,
            multiplier=Decimal("1.0"),
            effective_from=date(2026, 1, 1),
            exclusions=exclusions_list,
        )
        assert isinstance(rule.exclusions, tuple)
        exclusions_list.clear()
        assert len(rule.exclusions) == 1

    def test_rejects_unordered_set_for_exclusions(self) -> None:
        ex = RuleExclusion(
            exclusion_type=ExclusionType.CATEGORY,
            target="utilities",
            reason="Not eligible",
        )
        with pytest.raises(TypeError, match="must be an ordered sequence"):
            EarningRule(
                id=1,
                rule_key="nwcash.base",
                version=1,
                scope_type=ScopeType.BASE,
                multiplier=Decimal("1.0"),
                effective_from=date(2026, 1, 1),
                exclusions={ex},  # type: ignore[arg-type]
            )

    def test_numeric_and_date_validation(self) -> None:
        # Decimal required for multiplier
        with pytest.raises(TypeError, match="multiplier must be a Decimal instance"):
            EarningRule(
                id=1,
                rule_key="test",
                version=1,
                scope_type=ScopeType.BASE,
                multiplier=1.5,  # type: ignore[arg-type]
                effective_from=date(2026, 1, 1),
            )

        with pytest.raises(ValueError, match="cannot be negative"):
            EarningRule(
                id=1,
                rule_key="test",
                version=1,
                scope_type=ScopeType.BASE,
                multiplier=Decimal("-1.0"),
                effective_from=date(2026, 1, 1),
            )

        # Non-finite Decimals rejected
        for bad_val in (
            Decimal("NaN"),
            Decimal("sNaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with pytest.raises(ValueError, match="must be a finite number"):
                EarningRule(
                    id=1,
                    rule_key="test",
                    version=1,
                    scope_type=ScopeType.BASE,
                    multiplier=bad_val,
                    effective_from=date(2026, 1, 1),
                )

        # Min transaction cents must be integer
        with pytest.raises(TypeError, match="min_transaction_cents must be an integer"):
            EarningRule(
                id=1,
                rule_key="test",
                version=1,
                scope_type=ScopeType.BASE,
                multiplier=Decimal("1.0"),
                effective_from=date(2026, 1, 1),
                min_transaction_cents=25.5,  # type: ignore[arg-type]
            )

        with pytest.raises(ValueError, match="effective_to cannot precede effective_from"):
            EarningRule(
                id=1,
                rule_key="test",
                version=1,
                scope_type=ScopeType.BASE,
                multiplier=Decimal("1.0"),
                effective_from=date(2026, 6, 1),
                effective_to=date(2026, 5, 31),
            )


class TestSpendCap:
    """Tests for SpendCap dataclass and Cap alias."""

    def test_construction_and_immutability(self) -> None:
        assert Cap is SpendCap
        cap = SpendCap(
            cap_group_key="dining_quarterly",
            cap_amount_cents=50000,
            period=Period.QUARTERLY,
            description="$500 quarterly dining cap",
        )
        assert cap.cap_group_key == "dining_quarterly"
        assert cap.cap_amount_cents == 50000
        assert cap.period == Period.QUARTERLY

        with pytest.raises(FrozenInstanceError):
            cap.cap_amount_cents = 60000  # type: ignore[misc]

    def test_numeric_validation(self) -> None:
        with pytest.raises(ValueError, match="strictly positive"):
            SpendCap(
                cap_group_key="bad_cap",
                cap_amount_cents=0,
                period=Period.MONTHLY,
            )

        with pytest.raises(TypeError, match="cap_amount_cents must be an integer"):
            SpendCap(
                cap_group_key="bad_cap",
                cap_amount_cents=500.0,  # type: ignore[arg-type]
                period=Period.MONTHLY,
            )

        with pytest.raises(TypeError, match="cap_amount_cents must be an integer"):
            SpendCap(
                cap_group_key="bad_cap",
                cap_amount_cents=True,  # type: ignore[arg-type]
                period=Period.MONTHLY,
            )


class TestSpendHistory:
    """Tests for SpendHistory deep immutability and lookups."""

    def test_lookup_and_defaults(self) -> None:
        history = SpendHistory(
            cap_spend_cents={"dining_quarterly": 45000},
            threshold_spend_cents={"annual_spend": 250000},
        )
        assert history.get_cap_spend("dining_quarterly") == 45000
        assert history.get_cap_spend("unknown_cap") == 0
        assert history.get_threshold_spend("annual_spend") == 250000
        assert history.get_threshold_spend("unknown_thresh") == 0

    def test_deep_immutability(self) -> None:
        orig_caps = {"dining_quarterly": 45000}
        orig_thresh = {"annual_spend": 250000}
        history = SpendHistory(
            cap_spend_cents=orig_caps,
            threshold_spend_cents=orig_thresh,
        )

        # 1. Direct mutation on the exposed MappingProxyType must fail
        with pytest.raises(TypeError):
            history.cap_spend_cents["dining_quarterly"] = 99999  # type: ignore[index]

        with pytest.raises(TypeError):
            history.threshold_spend_cents["annual_spend"] = 99999  # type: ignore[index]

        # 2. Mutating the original external dictionary must not mutate history
        orig_caps["dining_quarterly"] = 11111
        orig_caps["new_cap"] = 22222
        orig_thresh["annual_spend"] = 33333

        assert history.get_cap_spend("dining_quarterly") == 45000
        assert history.get_cap_spend("new_cap") == 0
        assert history.get_threshold_spend("annual_spend") == 250000

    def test_invalid_spend_history_values(self) -> None:
        with pytest.raises(ValueError, match="non-negative integers"):
            SpendHistory(cap_spend_cents={"cap": -100})

        with pytest.raises(ValueError, match="non-negative integers"):
            SpendHistory(cap_spend_cents={"cap": 12.5})  # type: ignore[dict-item]

        with pytest.raises(ValueError, match="non-negative integers"):
            SpendHistory(cap_spend_cents={"cap": True})  # type: ignore[dict-item]


class TestValuation:
    """Tests for Valuation dataclass."""

    def test_construction_and_immutability(self) -> None:
        val = Valuation(
            reward_currency="NW_POINTS",
            cents_per_unit=Decimal("1.5000"),
            is_user_set=True,
        )
        assert val.reward_currency == "NW_POINTS"
        assert val.cents_per_unit == Decimal("1.5000")
        assert val.is_user_set is True

        with pytest.raises(FrozenInstanceError):
            val.cents_per_unit = Decimal("2.0")  # type: ignore[misc]

    def test_numeric_validation(self) -> None:
        with pytest.raises(ValueError, match="strictly positive"):
            Valuation(reward_currency="NW_POINTS", cents_per_unit=Decimal("0"))

        with pytest.raises(ValueError, match="strictly positive"):
            Valuation(reward_currency="NW_POINTS", cents_per_unit=Decimal("-1.0"))

        with pytest.raises(TypeError, match="cents_per_unit must be a Decimal instance"):
            Valuation(reward_currency="NW_POINTS", cents_per_unit=1.5)  # type: ignore[arg-type]

        # Non-finite Decimals rejected
        for bad_val in (
            Decimal("NaN"),
            Decimal("sNaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with pytest.raises(ValueError, match="must be a finite number"):
                Valuation(reward_currency="NW_POINTS", cents_per_unit=bad_val)


class TestCardEvaluationAndTrace:
    """Tests for CardEvaluation, TraceStep, and AppliedPortion."""

    def test_ranked_evaluation(self) -> None:
        portion = AppliedPortion(
            portion_cents=10000,
            rule_id=10,
            rule_key="nwcash.dining",
            rule_version=1,
            multiplier=Decimal("3.0"),
            reward_units=Decimal("300.00"),
        )
        step = TraceStep(
            step_number=1,
            step_type="selection",
            action="selected",
            detail="Category rule 'Dining 3x' won by specificity",
            rule_id=10,
            rule_key="nwcash.dining",
        )
        valuation = Valuation(
            reward_currency="NW_CASH",
            cents_per_unit=Decimal("1.0"),
            is_user_set=False,
        )
        portions_list = [portion]
        trace_list = [step]
        explanation_list = ["Earned 3.00 NW_CASH ($3.00)"]
        warnings_list = ["Cap nearly reached"]

        eval_res = CardEvaluation(
            card_id=1,
            card_name="Northwest Cash Rewards",
            reward_currency="NW_CASH",
            status=CardStatus.RANKED,
            reward_units=Decimal("3.00"),
            estimated_value_cents=300,
            valuation_used=valuation,
            applied_portions=portions_list,
            trace=trace_list,
            explanation=explanation_list,
            warnings=warnings_list,
        )
        assert eval_res.status == CardStatus.RANKED
        assert eval_res.estimated_value_cents == 300
        assert isinstance(eval_res.applied_portions, tuple)
        assert isinstance(eval_res.trace, tuple)
        assert isinstance(eval_res.explanation, tuple)
        assert isinstance(eval_res.warnings, tuple)

        # Deep immutability test: external mutations do not affect CardEvaluation
        portions_list.clear()
        trace_list.clear()
        explanation_list.clear()
        warnings_list.clear()
        assert len(eval_res.applied_portions) == 1
        assert len(eval_res.trace) == 1
        assert len(eval_res.explanation) == 1
        assert len(eval_res.warnings) == 1

    def test_rejects_unordered_set_in_card_evaluation(self) -> None:
        with pytest.raises(TypeError, match="must be an ordered sequence"):
            CardEvaluation(
                card_id=1,
                card_name="Test Card",
                reward_currency="NW_CASH",
                status=CardStatus.RANKED,
                reward_units=Decimal("100"),
                estimated_value_cents=100,
                explanation={"Earned reward"},  # type: ignore[arg-type]
            )

    def test_ranked_validation_rules(self) -> None:
        with pytest.raises(ValueError, match="must have estimated_value_cents"):
            CardEvaluation(
                card_id=1,
                card_name="Test Card",
                reward_currency="NW_CASH",
                status=CardStatus.RANKED,
                reward_units=Decimal("100"),
                estimated_value_cents=None,
            )

        with pytest.raises(ValueError, match="cannot have rejection_reason"):
            CardEvaluation(
                card_id=1,
                card_name="Test Card",
                reward_currency="NW_CASH",
                status=CardStatus.RANKED,
                reward_units=Decimal("100"),
                estimated_value_cents=100,
                rejection_reason="some_reason",
            )

    def test_unranked_validation_rules(self) -> None:
        with pytest.raises(ValueError, match="cannot have estimated_value_cents"):
            CardEvaluation(
                card_id=2,
                card_name="Skyward Miles Card",
                reward_currency="SKY_MILES",
                status=CardStatus.UNRANKED,
                reward_units=Decimal("400"),
                estimated_value_cents=400,
                rejection_reason=UnrankedReason.NO_VALUATION.value,
            )

        with pytest.raises(ValueError, match="must specify a rejection_reason"):
            CardEvaluation(
                card_id=2,
                card_name="Skyward Miles Card",
                reward_currency="SKY_MILES",
                status=CardStatus.UNRANKED,
                reward_units=Decimal("400"),
                estimated_value_cents=None,
                rejection_reason=None,
            )

        with pytest.raises(ValueError, match="rejection_reason must be no_valuation"):
            CardEvaluation(
                card_id=2,
                card_name="Skyward Miles Card",
                reward_currency="SKY_MILES",
                status=CardStatus.UNRANKED,
                reward_units=Decimal("400"),
                estimated_value_cents=None,
                rejection_reason="arbitrary_reason",
            )

    def test_ineligible_validation_rules(self) -> None:
        with pytest.raises(ValueError, match="0 reward units"):
            CardEvaluation(
                card_id=3,
                card_name="Inactive Card",
                reward_currency="NW_CASH",
                status=CardStatus.INELIGIBLE,
                reward_units=Decimal("50"),
                rejection_reason=IneligibleReason.NO_EFFECTIVE_RULE.value,
            )

        with pytest.raises(ValueError, match="must specify a rejection_reason"):
            CardEvaluation(
                card_id=3,
                card_name="Inactive Card",
                reward_currency="NW_CASH",
                status=CardStatus.INELIGIBLE,
                reward_units=Decimal("0"),
                rejection_reason=None,
            )

        with pytest.raises(ValueError, match="rejection_reason must be one of"):
            CardEvaluation(
                card_id=3,
                card_name="Inactive Card",
                reward_currency="NW_CASH",
                status=CardStatus.INELIGIBLE,
                reward_units=Decimal("0"),
                rejection_reason="invalid_reason",
            )

    def test_numeric_type_and_finiteness_enforcement(self) -> None:
        # Rejects float for reward_units
        with pytest.raises(TypeError, match="reward_units must be a Decimal instance"):
            CardEvaluation(
                card_id=1,
                card_name="Test Card",
                reward_currency="NW_CASH",
                status=CardStatus.RANKED,
                reward_units=1.5,  # type: ignore[arg-type]
                estimated_value_cents=150,
            )

        # Rejects non-finite Decimal for reward_units
        for bad_val in (
            Decimal("NaN"),
            Decimal("sNaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with pytest.raises(ValueError, match="must be a finite number"):
                CardEvaluation(
                    card_id=1,
                    card_name="Test Card",
                    reward_currency="NW_CASH",
                    status=CardStatus.RANKED,
                    reward_units=bad_val,
                    estimated_value_cents=150,
                )

        # Rejects float for estimated_value_cents
        err_match = "estimated_value_cents must be a non-negative integer"
        with pytest.raises(ValueError, match=err_match):
            CardEvaluation(
                card_id=1,
                card_name="Test Card",
                reward_currency="NW_CASH",
                status=CardStatus.RANKED,
                reward_units=Decimal("1.5"),
                estimated_value_cents=150.5,  # type: ignore[arg-type]
            )

        # Rejects negative estimated_value_cents
        with pytest.raises(ValueError, match=err_match):
            CardEvaluation(
                card_id=1,
                card_name="Test Card",
                reward_currency="NW_CASH",
                status=CardStatus.RANKED,
                reward_units=Decimal("1.5"),
                estimated_value_cents=-10,
            )


class TestCardContext:
    """Tests for CardContext assembly container."""

    def test_construction_and_immutability(self) -> None:
        rule = EarningRule(
            id=1,
            rule_key="base.rule",
            version=1,
            scope_type=ScopeType.BASE,
            multiplier=Decimal("1.0"),
            effective_from=date(2026, 1, 1),
        )
        cap = SpendCap(
            cap_group_key="annual_cap",
            cap_amount_cents=100000,
            period=Period.CALENDAR_YEAR,
        )
        rules_list = [rule]
        caps_list = [cap]

        context = CardContext(
            card_id=10,
            card_name="Northwest Premier",
            reward_currency="NW_POINTS",
            rules=rules_list,
            caps=caps_list,
        )
        assert context.card_id == 10
        assert isinstance(context.rules, tuple)
        assert isinstance(context.caps, tuple)

        with pytest.raises(FrozenInstanceError):
            context.card_name = "New Name"  # type: ignore[misc]

        # Deep immutability test
        rules_list.clear()
        caps_list.clear()
        assert len(context.rules) == 1
        assert len(context.caps) == 1

    def test_rejects_unordered_set_for_rules_and_caps(self) -> None:
        rule = EarningRule(
            id=1,
            rule_key="base.rule",
            version=1,
            scope_type=ScopeType.BASE,
            multiplier=Decimal("1.0"),
            effective_from=date(2026, 1, 1),
        )
        with pytest.raises(TypeError, match="must be an ordered sequence"):
            CardContext(
                card_id=10,
                card_name="Northwest Premier",
                reward_currency="NW_POINTS",
                rules={rule},  # type: ignore[arg-type]
            )
