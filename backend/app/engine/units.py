"""Reward unit calculation and transaction-level rounding (T16).

Converts cap-allocated portions into AppliedPortion records using exact Decimal
arithmetic, sums all unrounded portion units, and applies the primary rule's
rounding mode once at the transaction level.
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from app.engine.caps import CapPortion
from app.engine.types import (
    AppliedPortion,
    RoundingMode,
    TraceStep,
    _normalize_sequence,
    _validate_decimal,
)

_CENTS_PER_DOLLAR = Decimal("100")
_WHOLE_UNIT = Decimal("1")
_FOUR_DP = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class UnitsResult:
    """Result of per-portion unit calculation and transaction-level rounding."""

    applied_portions: Sequence[AppliedPortion]
    unrounded_total_units: Decimal
    total_reward_units: Decimal
    rounding_mode_used: RoundingMode
    trace_step: TraceStep

    def __post_init__(self) -> None:
        _validate_decimal(self.unrounded_total_units, "unrounded_total_units", allow_zero=True)
        _validate_decimal(self.total_reward_units, "total_reward_units", allow_zero=True)
        object.__setattr__(
            self,
            "applied_portions",
            _normalize_sequence(self.applied_portions, "applied_portions"),
        )


def _apply_rounding(total_units: Decimal, rounding_mode: RoundingMode) -> Decimal:
    """Apply transaction-level rounding mode to the summed unrounded units."""
    if rounding_mode == RoundingMode.FLOOR_UNITS:
        return total_units.quantize(_WHOLE_UNIT, rounding=ROUND_FLOOR)
    if rounding_mode == RoundingMode.NEAREST_UNIT:
        return total_units.quantize(_WHOLE_UNIT, rounding=ROUND_HALF_UP)
    if rounding_mode == RoundingMode.NONE_4DP:
        return total_units.quantize(_FOUR_DP, rounding=ROUND_HALF_UP)
    raise ValueError(f"Unsupported rounding mode: {rounding_mode}")


def calculate_reward_units(portions: Sequence[CapPortion]) -> UnitsResult:
    """Calculate unrounded per-portion units and apply transaction-level rounding once.

    Uses the first portion's rule rounding mode as the transaction-level rounding mode.
    Raises ValueError if portions is empty or rounding mode is unsupported.
    """
    normalized_portions = _normalize_sequence(portions, "portions")
    if not normalized_portions:
        raise ValueError("portions must not be empty")

    applied_portions: list[AppliedPortion] = []
    unrounded_total = Decimal("0")

    for portion in normalized_portions:
        part_units = (Decimal(portion.amount_cents) / _CENTS_PER_DOLLAR) * portion.rule.multiplier
        unrounded_total += part_units
        applied_portions.append(
            AppliedPortion(
                portion_cents=portion.amount_cents,
                rule_id=portion.rule.id,
                rule_key=portion.rule.rule_key,
                rule_version=portion.rule.version,
                multiplier=portion.rule.multiplier,
                reward_units=part_units,
                cap_group_key=portion.cap_group_key,
            )
        )

    primary_rule = normalized_portions[0].rule
    rounding_mode = primary_rule.rounding
    total_units = _apply_rounding(unrounded_total, rounding_mode)

    trace_step = TraceStep(
        step_number=1,
        step_type="units_calculation",
        action="calculated",
        rule_id=primary_rule.id,
        rule_key=primary_rule.rule_key,
        detail=(
            f"Calculated {len(applied_portions)} portion(s) totaling "
            f"{unrounded_total} unrounded units; applied {rounding_mode.value} "
            f"rounding -> {total_units} units."
        ),
    )

    return UnitsResult(
        applied_portions=tuple(applied_portions),
        unrounded_total_units=unrounded_total,
        total_reward_units=total_units,
        rounding_mode_used=rounding_mode,
        trace_step=trace_step,
    )
