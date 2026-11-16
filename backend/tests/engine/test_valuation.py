"""Table-driven unit tests for reward valuation and no-valuation routing (T17, AC-2).

Validates Decimal valuation math with ROUND_HALF_EVEN, exact and fractional
cent rounding (including half-even ties rounding both up and down), zero reward
units, illustrative default valuation warnings, currency normalization and
mismatch errors, no-valuation routing to UNRANKED, float/bool rejection,
immutability, and deterministic trace output.
"""

from decimal import Decimal

import pytest

from app.engine.types import (
    CardStatus,
    UnrankedReason,
    Valuation,
)
from app.engine.valuation import ValuationResult, evaluate_valuation


class TestValuationPresent:
    """Table-driven tests when a Valuation is provided."""

    @pytest.mark.parametrize(
        ("reward_units", "cents_per_unit", "expected_cents"),
        [
            # Exact integer cents
            (Decimal("100"), Decimal("1.0"), 100),
            (Decimal("300"), Decimal("1.5"), 450),
            (Decimal("0"), Decimal("1.5"), 0),
            (Decimal("0.0000"), Decimal("2.0"), 0),
            # Half-even ties: 0.5 -> 0 (even), 1.5 -> 2 (even), 2.5 -> 2 (even), 3.5 -> 4 (even)
            (Decimal("1"), Decimal("0.5"), 0),
            (Decimal("1"), Decimal("1.5"), 2),
            (Decimal("1"), Decimal("2.5"), 2),
            (Decimal("1"), Decimal("3.5"), 4),
            # Non-tie fractional rounding
            (Decimal("100"), Decimal("1.234"), 123),
            (Decimal("100"), Decimal("1.236"), 124),
        ],
    )
    def test_valuation_math_and_half_even_rounding(
        self,
        reward_units: Decimal,
        cents_per_unit: Decimal,
        expected_cents: int,
    ) -> None:
        val = Valuation(
            reward_currency="SKY_MILES",
            cents_per_unit=cents_per_unit,
            is_user_set=True,
        )

        result = evaluate_valuation(reward_units, "SKY_MILES", val)

        assert isinstance(result, ValuationResult)
        assert result.status == CardStatus.RANKED
        assert result.estimated_value_cents == expected_cents
        assert result.valuation_used == val
        assert result.rejection_reason is None
        assert result.rejection_message is None
        assert result.warnings == ()
        assert result.trace_step.step_number == 1
        assert result.trace_step.step_type == "valuation"
        assert result.trace_step.action == "valued"
        assert "SKY_MILES" in result.trace_step.detail
        assert str(reward_units) in result.trace_step.detail
        assert str(cents_per_unit) in result.trace_step.detail
        assert str(expected_cents) in result.trace_step.detail

    def test_default_valuation_emits_illustrative_warning(self) -> None:
        default_val = Valuation(
            reward_currency="POINTS",
            cents_per_unit=Decimal("1.0"),
            is_user_set=False,
        )
        res_default = evaluate_valuation(Decimal("500"), "POINTS", default_val)
        assert res_default.warnings == ("illustrative default valuation",)

        user_val = Valuation(
            reward_currency="POINTS",
            cents_per_unit=Decimal("1.0"),
            is_user_set=True,
        )
        res_user = evaluate_valuation(Decimal("500"), "POINTS", user_val)
        assert res_user.warnings == ()

    def test_currency_normalization_and_mismatch(self) -> None:
        val = Valuation(
            reward_currency="  sky_miles  ",
            cents_per_unit=Decimal("1.5"),
            is_user_set=True,
        )
        res = evaluate_valuation(Decimal("200"), "SKY_MILES", val)
        assert res.status == CardStatus.RANKED
        assert res.estimated_value_cents == 300

        mismatched = Valuation(
            reward_currency="CASH_USD",
            cents_per_unit=Decimal("1.0"),
            is_user_set=True,
        )
        with pytest.raises(ValueError, match="does not match"):
            evaluate_valuation(Decimal("200"), "SKY_MILES", mismatched)


class TestNoValuationRouting:
    """Tests when Valuation is None (AC-2 cross-currency honesty)."""

    def test_none_valuation_routes_to_unranked_with_documented_message(self) -> None:
        # Even with a huge number of raw reward units, missing valuation must remain UNRANKED
        result = evaluate_valuation(Decimal("99999"), "Skyward Miles", None)

        assert result.status == CardStatus.UNRANKED
        assert result.estimated_value_cents is None
        assert result.valuation_used is None
        assert result.rejection_reason == UnrankedReason.NO_VALUATION.value
        assert result.rejection_message == (
            "No estimated value is set for Skyward Miles, so this card cannot be "
            "reliably compared in dollars. Set a valuation in Settings."
        )
        assert result.warnings == ()
        assert result.trace_step.step_number == 1
        assert result.trace_step.step_type == "valuation"
        assert result.trace_step.action == "unranked"
        assert result.trace_step.reason == UnrankedReason.NO_VALUATION.value
        assert "Skyward Miles" in result.trace_step.detail
        assert "99999" in result.trace_step.detail


class TestValidationImmutabilityAndDeterminism:
    """Tests for float/bool rejection, empty currency, immutability, and determinism."""

    def test_rejects_float_bool_and_empty_currency(self) -> None:
        with pytest.raises(TypeError, match="Decimal"):
            evaluate_valuation(100.0, "CASH_USD", None)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Decimal"):
            evaluate_valuation(True, "CASH_USD", None)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="reward_currency"):
            evaluate_valuation(Decimal("100"), "   ", None)

    def test_valuation_result_rejects_float_bool_and_set_warnings(self) -> None:
        base_res = evaluate_valuation(Decimal("100"), "CASH_USD", None)

        with pytest.raises(ValueError, match="non-negative integer"):
            ValuationResult(
                status=CardStatus.RANKED,
                estimated_value_cents=True,  # type: ignore[arg-type]
                valuation_used=None,
                rejection_reason=None,
                rejection_message=None,
                warnings=(),
                trace_step=base_res.trace_step,
            )

        with pytest.raises(ValueError, match="non-negative integer"):
            ValuationResult(
                status=CardStatus.RANKED,
                estimated_value_cents=100.5,  # type: ignore[arg-type]
                valuation_used=None,
                rejection_reason=None,
                rejection_message=None,
                warnings=(),
                trace_step=base_res.trace_step,
            )

        with pytest.raises(TypeError, match="set"):
            ValuationResult(
                status=CardStatus.UNRANKED,
                estimated_value_cents=None,
                valuation_used=None,
                rejection_reason=UnrankedReason.NO_VALUATION.value,
                rejection_message="No valuation",
                warnings={"warn"},  # type: ignore[arg-type]
                trace_step=base_res.trace_step,
            )

    def test_determinism_and_immutability(self) -> None:
        val = Valuation("POINTS", Decimal("1.25"), is_user_set=False)
        r1 = evaluate_valuation(Decimal("250"), "POINTS", val)
        r2 = evaluate_valuation(Decimal("250"), "POINTS", val)

        assert r1 == r2
        with pytest.raises(AttributeError):
            r1.estimated_value_cents = 999  # type: ignore[misc]
