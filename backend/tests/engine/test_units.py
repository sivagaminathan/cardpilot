"""Table-driven unit tests for reward unit calculation and rounding modes (T16).

Validates per-portion Decimal unit math, transaction-level rounding once on
the summed portions (FLOOR_UNITS, NEAREST_UNIT, NONE_4DP), half cases,
straddled purchases with differing rule rounding modes, empty/invalid input
handling, determinism, and runtime immutability.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine.caps import CapPortion
from app.engine.types import (
    AppliedPortion,
    EarningRule,
    RoundingMode,
    ScopeType,
)
from app.engine.units import UnitsResult, calculate_reward_units


def _make_rule(
    id: int,
    rule_key: str,
    multiplier: str,
    rounding: RoundingMode = RoundingMode.FLOOR_UNITS,
    scope_type: ScopeType = ScopeType.BASE,
    cap_group_key: str | None = None,
) -> EarningRule:
    return EarningRule(
        id=id,
        rule_key=rule_key,
        version=1,
        scope_type=scope_type,
        multiplier=Decimal(multiplier),
        effective_from=date(2026, 1, 1),
        rounding=rounding,
        cap_group_key=cap_group_key,
    )


class TestRoundingModesAndHalfCases:
    """Table-driven tests for FLOOR_UNITS, NEAREST_UNIT, and NONE_4DP."""

    @pytest.mark.parametrize(
        ("amount_cents", "multiplier", "rounding", "expected_unrounded", "expected_total"),
        [
            # Exact integer values across all three modes
            (1000, "2.0", RoundingMode.FLOOR_UNITS, Decimal("20.0"), Decimal("20")),
            (1000, "2.0", RoundingMode.NEAREST_UNIT, Decimal("20.0"), Decimal("20")),
            (1000, "2.0", RoundingMode.NONE_4DP, Decimal("20.0"), Decimal("20.0000")),
            # FLOOR_UNITS: fractional and half cases round down
            (100, "0.5", RoundingMode.FLOOR_UNITS, Decimal("0.5"), Decimal("0")),
            (300, "0.5", RoundingMode.FLOOR_UNITS, Decimal("1.5"), Decimal("1")),
            (500, "0.5", RoundingMode.FLOOR_UNITS, Decimal("2.5"), Decimal("2")),
            (700, "0.5", RoundingMode.FLOOR_UNITS, Decimal("3.5"), Decimal("3")),
            (199, "1.0", RoundingMode.FLOOR_UNITS, Decimal("1.99"), Decimal("1")),
            # NEAREST_UNIT (ROUND_HALF_UP): 0.5->1, 1.5->2, 2.5->3, 3.5->4, 1.49->1
            (100, "0.5", RoundingMode.NEAREST_UNIT, Decimal("0.5"), Decimal("1")),
            (300, "0.5", RoundingMode.NEAREST_UNIT, Decimal("1.5"), Decimal("2")),
            (500, "0.5", RoundingMode.NEAREST_UNIT, Decimal("2.5"), Decimal("3")),
            (700, "0.5", RoundingMode.NEAREST_UNIT, Decimal("3.5"), Decimal("4")),
            (149, "1.0", RoundingMode.NEAREST_UNIT, Decimal("1.49"), Decimal("1")),
            # NONE_4DP: 4 decimal places with ROUND_HALF_UP
            (100, "1.5", RoundingMode.NONE_4DP, Decimal("1.5"), Decimal("1.5000")),
            (1234, "3.0", RoundingMode.NONE_4DP, Decimal("37.02"), Decimal("37.0200")),
            (1, "0.005", RoundingMode.NONE_4DP, Decimal("0.00005"), Decimal("0.0001")),
            (1, "0.004", RoundingMode.NONE_4DP, Decimal("0.00004"), Decimal("0.0000")),
            (3, "0.005", RoundingMode.NONE_4DP, Decimal("0.00015"), Decimal("0.0002")),
        ],
    )
    def test_single_portion_rounding_modes(
        self,
        amount_cents: int,
        multiplier: str,
        rounding: RoundingMode,
        expected_unrounded: Decimal,
        expected_total: Decimal,
    ) -> None:
        rule = _make_rule(1, "test.rule", multiplier=multiplier, rounding=rounding)
        portion = CapPortion(rule=rule, amount_cents=amount_cents)

        result = calculate_reward_units((portion,))

        assert isinstance(result, UnitsResult)
        assert result.unrounded_total_units == expected_unrounded
        assert result.total_reward_units == expected_total
        assert str(result.total_reward_units) == str(expected_total)
        assert result.rounding_mode_used == rounding
        assert result.applied_portions == (
            AppliedPortion(
                portion_cents=amount_cents,
                rule_id=1,
                rule_key="test.rule",
                rule_version=1,
                multiplier=Decimal(multiplier),
                reward_units=expected_unrounded,
                cap_group_key=None,
            ),
        )
        assert result.trace_step.step_number == 1
        assert result.trace_step.step_type == "units_calculation"
        assert result.trace_step.action == "calculated"
        assert result.trace_step.rule_id == 1
        assert result.trace_step.rule_key == "test.rule"
        assert rounding.value in result.trace_step.detail
        assert str(expected_total) in result.trace_step.detail


class TestMultiPortionRoundingOnce:
    """Tests that rounding is applied once to the sum and uses the first portion's mode."""

    def test_multi_portion_sums_before_floor_rounding(self) -> None:
        """Two portions of 1.6 units each sum to 3.2 -> floor=3 (not 1 + 1 = 2)."""
        r_capped = _make_rule(
            id=1,
            rule_key="dining.2x",
            multiplier="2.0",
            rounding=RoundingMode.FLOOR_UNITS,
            scope_type=ScopeType.CATEGORY,
            cap_group_key="dining_q",
        )
        r_base = _make_rule(
            id=2,
            rule_key="base.1x",
            multiplier="1.0",
            rounding=RoundingMode.FLOOR_UNITS,
            scope_type=ScopeType.BASE,
        )
        p1 = CapPortion(rule=r_capped, amount_cents=80, cap_group_key="dining_q")  # 1.6
        p2 = CapPortion(rule=r_base, amount_cents=160, cap_group_key=None)  # 1.6

        result = calculate_reward_units((p1, p2))

        assert result.unrounded_total_units == Decimal("3.2")
        assert result.total_reward_units == Decimal("3")
        assert [ap.reward_units for ap in result.applied_portions] == [
            Decimal("1.6"),
            Decimal("1.6"),
        ]

    @pytest.mark.parametrize(
        ("first_mode", "second_mode", "expected_total"),
        [
            (RoundingMode.FLOOR_UNITS, RoundingMode.NEAREST_UNIT, Decimal("2")),
            (RoundingMode.NEAREST_UNIT, RoundingMode.FLOOR_UNITS, Decimal("3")),
            (RoundingMode.NONE_4DP, RoundingMode.FLOOR_UNITS, Decimal("2.5000")),
        ],
    )
    def test_straddled_purchase_uses_first_portions_rounding_mode(
        self,
        first_mode: RoundingMode,
        second_mode: RoundingMode,
        expected_total: Decimal,
    ) -> None:
        r1 = _make_rule(
            id=1,
            rule_key="dining.5x",
            multiplier="5.0",
            rounding=first_mode,
            scope_type=ScopeType.CATEGORY,
            cap_group_key="dining_q",
        )
        r2 = _make_rule(
            id=2,
            rule_key="base.1x",
            multiplier="1.0",
            rounding=second_mode,
            scope_type=ScopeType.BASE,
        )
        # 30 cents * 5x = 1.50; 100 cents * 1x = 1.00; sum = 2.50
        p1 = CapPortion(rule=r1, amount_cents=30, cap_group_key="dining_q")
        p2 = CapPortion(rule=r2, amount_cents=100, cap_group_key=None)

        result = calculate_reward_units((p1, p2))

        assert result.unrounded_total_units == Decimal("2.5")
        assert result.total_reward_units == expected_total
        assert result.rounding_mode_used == first_mode


class TestValidationDeterminismAndImmutability:
    """Tests for empty/invalid inputs, Decimal precision, determinism, and immutability."""

    def test_empty_portions_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            calculate_reward_units(())

    def test_unordered_set_portions_rejected(self) -> None:
        rule = _make_rule(1, "r1", multiplier="1.0")
        portion = CapPortion(rule=rule, amount_cents=100)

        with pytest.raises(TypeError, match="set"):
            calculate_reward_units({portion})  # type: ignore[arg-type]

    def test_unsupported_rounding_mode_raises_value_error(self) -> None:
        rule = _make_rule(1, "r1", multiplier="1.0")
        object.__setattr__(rule, "rounding", "invalid_mode")
        portion = CapPortion(rule=rule, amount_cents=100)

        with pytest.raises(ValueError, match="Unsupported rounding mode"):
            calculate_reward_units((portion,))

    def test_units_result_rejects_float_and_bool_totals(self) -> None:
        rule = _make_rule(1, "r1", multiplier="1.0")
        res = calculate_reward_units((CapPortion(rule=rule, amount_cents=100),))

        with pytest.raises(TypeError, match="Decimal"):
            UnitsResult(
                applied_portions=res.applied_portions,
                unrounded_total_units=1.0,  # type: ignore[arg-type]
                total_reward_units=Decimal("1"),
                rounding_mode_used=RoundingMode.FLOOR_UNITS,
                trace_step=res.trace_step,
            )

        with pytest.raises(TypeError, match="Decimal"):
            UnitsResult(
                applied_portions=res.applied_portions,
                unrounded_total_units=Decimal("1"),
                total_reward_units=True,  # type: ignore[arg-type]
                rounding_mode_used=RoundingMode.FLOOR_UNITS,
                trace_step=res.trace_step,
            )

    def test_determinism_and_immutability(self) -> None:
        rule = _make_rule(1, "r1", multiplier="2.5", rounding=RoundingMode.NEAREST_UNIT)
        portion = CapPortion(rule=rule, amount_cents=100)

        r1 = calculate_reward_units((portion,))
        r2 = calculate_reward_units((portion,))
        assert r1 == r2

        with pytest.raises(AttributeError):
            r1.total_reward_units = Decimal("99")  # type: ignore[misc]

        with pytest.raises(TypeError, match="set"):
            UnitsResult(
                applied_portions={r1.applied_portions[0]},  # type: ignore[arg-type]
                unrounded_total_units=Decimal("2.5"),
                total_reward_units=Decimal("3"),
                rounding_mode_used=RoundingMode.NEAREST_UNIT,
                trace_step=r1.trace_step,
            )
