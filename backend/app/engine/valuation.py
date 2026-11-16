"""Valuation calculation and no-valuation routing for the reward engine (T17, AC-2).

Converts rounded reward units into estimated USD cents using ROUND_HALF_EVEN
when a Valuation is present, or routes the card to CardStatus.UNRANKED with
UnrankedReason.NO_VALUATION and the documented limitation message when absent.
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from app.engine.types import (
    CardStatus,
    TraceStep,
    UnrankedReason,
    Valuation,
    _normalize_sequence,
    _validate_decimal,
)

_WHOLE_CENT = Decimal("1")


@dataclass(frozen=True, slots=True)
class ValuationResult:
    """Result of valuing reward units or routing to unranked when no valuation exists."""

    status: CardStatus
    estimated_value_cents: int | None
    valuation_used: Valuation | None
    rejection_reason: str | None
    rejection_message: str | None
    warnings: Sequence[str]
    trace_step: TraceStep

    def __post_init__(self) -> None:
        if self.estimated_value_cents is not None and (
            not isinstance(self.estimated_value_cents, int)
            or isinstance(self.estimated_value_cents, bool)
            or self.estimated_value_cents < 0
        ):
            raise ValueError("estimated_value_cents must be a non-negative integer or None")

        if self.status == CardStatus.RANKED:
            if self.estimated_value_cents is None:
                raise ValueError("Ranked valuation result must have estimated_value_cents")
            if self.rejection_reason is not None:
                raise ValueError("Ranked valuation result cannot have rejection_reason")
        elif self.status == CardStatus.UNRANKED:
            if self.estimated_value_cents is not None:
                raise ValueError("Unranked valuation result cannot have estimated_value_cents")
            if self.rejection_reason != UnrankedReason.NO_VALUATION.value:
                raise ValueError(
                    "Unranked valuation result rejection_reason must be "
                    f"{UnrankedReason.NO_VALUATION.value!r}"
                )
        else:
            raise ValueError(
                f"ValuationResult status must be RANKED or UNRANKED, got {self.status!r}"
            )

        object.__setattr__(
            self,
            "warnings",
            _normalize_sequence(self.warnings, "warnings"),
        )


def _normalize_currency(value: str) -> str:
    """Normalize reward currency string for case-insensitive, whitespace-trimmed comparison."""
    return value.strip().casefold()


def evaluate_valuation(
    reward_units: Decimal,
    reward_currency: str,
    valuation: Valuation | None,
) -> ValuationResult:
    """Compute estimated value in cents or route to UNRANKED when valuation is absent.

    Args:
        reward_units: Transaction-level reward units (typically UnitsResult.total_reward_units).
        reward_currency: Currency label for the card's earned units.
        valuation: Optional Valuation matching reward_currency.

    Returns:
        ValuationResult with CardStatus.RANKED and ROUND_HALF_EVEN integer cents,
        or CardStatus.UNRANKED with UnrankedReason.NO_VALUATION.
    """
    _validate_decimal(reward_units, "reward_units", allow_zero=True)
    currency_label = reward_currency.strip()
    if not currency_label:
        raise ValueError("reward_currency must not be empty")

    if valuation is None:
        message = (
            f"No estimated value is set for {currency_label}, so this card cannot be "
            "reliably compared in dollars. Set a valuation in Settings."
        )
        trace_step = TraceStep(
            step_number=1,
            step_type="valuation",
            action="unranked",
            reason=UnrankedReason.NO_VALUATION.value,
            detail=f"Cannot value {reward_units} {currency_label} units: {message}",
        )
        return ValuationResult(
            status=CardStatus.UNRANKED,
            estimated_value_cents=None,
            valuation_used=None,
            rejection_reason=UnrankedReason.NO_VALUATION.value,
            rejection_message=message,
            warnings=(),
            trace_step=trace_step,
        )

    if _normalize_currency(valuation.reward_currency) != _normalize_currency(currency_label):
        raise ValueError(
            f"Valuation currency '{valuation.reward_currency}' does not match "
            f"reward_currency '{reward_currency}'."
        )

    raw_cents = reward_units * valuation.cents_per_unit
    estimated_cents = int(raw_cents.quantize(_WHOLE_CENT, rounding=ROUND_HALF_EVEN))
    warnings: tuple[str, ...] = (
        ("illustrative default valuation",) if not valuation.is_user_set else ()
    )

    trace_step = TraceStep(
        step_number=1,
        step_type="valuation",
        action="valued",
        detail=(
            f"Valued {reward_units} {currency_label} units at "
            f"{valuation.cents_per_unit} cents/unit -> {estimated_cents} cents."
        ),
    )

    return ValuationResult(
        status=CardStatus.RANKED,
        estimated_value_cents=estimated_cents,
        valuation_used=valuation,
        rejection_reason=None,
        rejection_message=None,
        warnings=warnings,
        trace_step=trace_step,
    )
