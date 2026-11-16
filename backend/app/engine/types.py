"""Domain types for the pure reward calculation engine (T08).

Pure, deterministic data structures modeling credit card rewards calculations.
Contains no database, network, clock, or I/O side effects.
All monetary amounts are represented as integer cents.
All reward multipliers and valuations are represented as Decimal.
Floating-point arithmetic and float types are strictly prohibited.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeVar

T = TypeVar("T")


def _validate_cents(value: Any, field_name: str) -> None:
    """Validate that a monetary cent field is a strictly positive integer, rejecting bool."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{field_name} must be strictly positive")


def _validate_decimal(value: Any, field_name: str, allow_zero: bool = True) -> None:
    """Validate that a rate or valuation field is a finite Decimal instance."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal instance, got {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be a finite number, got {value!r}")
    if allow_zero:
        if value < Decimal("0"):
            raise ValueError(f"{field_name} cannot be negative")
    else:
        if value <= Decimal("0"):
            raise ValueError(f"{field_name} must be strictly positive")


def _normalize_sequence(value: Sequence[T], field_name: str) -> tuple[T, ...]:
    """Validate that a collection is an ordered sequence (tuple or list) and convert to tuple."""
    if isinstance(value, (set, frozenset)):
        raise TypeError(f"{field_name} must be an ordered sequence (tuple or list), not a set")
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list, got {type(value).__name__}")
    return tuple(value)


class ScopeType(StrEnum):
    """Scope level of an earning rule determining selection specificity."""

    BASE = "base"
    CATEGORY = "category"
    MERCHANT = "merchant"


class Period(StrEnum):
    """Tracking period for spend caps and threshold evaluations."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CALENDAR_YEAR = "calendar_year"
    CARD_YEAR = "card_year"


class RoundingMode(StrEnum):
    """Rounding mode applied to total transaction reward units."""

    FLOOR_UNITS = "floor_units"
    NEAREST_UNIT = "nearest_unit"
    NONE_4DP = "none_4dp"


class PostCapBehavior(StrEnum):
    """Behavior applied when spend exceeds an allocated spend cap."""

    FALLBACK_TO_BASE = "fallback_to_base"


class ExclusionType(StrEnum):
    """Target entity type for rule exclusions."""

    CATEGORY = "category"
    MERCHANT = "merchant"
    MERCHANT_TAG = "merchant_tag"


class CardStatus(StrEnum):
    """Status classification of a card in recommendation results."""

    RANKED = "ranked"
    UNRANKED = "unranked"
    INELIGIBLE = "ineligible"


class UnrankedReason(StrEnum):
    """Reason why an eligible card cannot be ranked across currencies."""

    NO_VALUATION = "no_valuation"


class IneligibleReason(StrEnum):
    """Reason why a card is ineligible for a given purchase."""

    NO_EFFECTIVE_RULE = "no_effective_rule"
    NO_APPLICABLE_RULE = "no_applicable_rule"


@dataclass(frozen=True, slots=True)
class RuleExclusion:
    """An exclusion criteria attached to an earning rule."""

    exclusion_type: ExclusionType
    target: str
    reason: str


@dataclass(frozen=True, slots=True)
class SpendCap:
    """Spend cap defining maximum eligible spend per tracking period."""

    cap_group_key: str
    cap_amount_cents: int
    period: Period
    description: str = ""

    def __post_init__(self) -> None:
        _validate_cents(self.cap_amount_cents, "cap_amount_cents")


# Backlog alias
Cap = SpendCap


@dataclass(frozen=True, slots=True)
class EarningRule:
    """A versioned, immutable earning rule for a card product."""

    id: int
    rule_key: str
    version: int
    scope_type: ScopeType
    multiplier: Decimal
    effective_from: date
    category: str | None = None
    merchant: str | None = None
    priority: int = 0
    cap_group_key: str | None = None
    post_cap_behavior: PostCapBehavior = PostCapBehavior.FALLBACK_TO_BASE
    min_transaction_cents: int | None = None
    min_period_spend_cents: int | None = None
    threshold_period: Period | None = None
    rounding: RoundingMode = RoundingMode.FLOOR_UNITS
    effective_to: date | None = None
    exclusions: Sequence[RuleExclusion] = ()
    source_id: int | None = None
    last_reviewed_on: date | None = None
    description: str = ""

    def __post_init__(self) -> None:
        _validate_decimal(self.multiplier, "multiplier", allow_zero=True)
        if self.min_transaction_cents is not None:
            _validate_cents(self.min_transaction_cents, "min_transaction_cents")
        if self.min_period_spend_cents is not None:
            _validate_cents(self.min_period_spend_cents, "min_period_spend_cents")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        # Enforce deep immutability and sequence determinism
        object.__setattr__(self, "exclusions", _normalize_sequence(self.exclusions, "exclusions"))


# Backlog alias
Rule = EarningRule


@dataclass(frozen=True, slots=True)
class Purchase:
    """A purchase context submitted for reward evaluation."""

    amount_cents: int
    category: str
    purchase_date: date
    merchant: str | None = None
    merchant_tags: Sequence[str] = ()

    def __post_init__(self) -> None:
        _validate_cents(self.amount_cents, "amount_cents")
        # Enforce deep immutability and sequence determinism
        object.__setattr__(
            self,
            "merchant_tags",
            _normalize_sequence(self.merchant_tags, "merchant_tags"),
        )


@dataclass(frozen=True, slots=True)
class SpendHistory:
    """Prior spend across tracking periods as of the purchase date."""

    cap_spend_cents: Mapping[str, int] = field(default_factory=dict)
    threshold_spend_cents: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate values and defensively copy into a read-only MappingProxyType
        copied_caps: dict[str, int] = {}
        for k, v in self.cap_spend_cents.items():
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(
                    f"cap_spend_cents values must be non-negative integers, got {v!r} for key {k!r}"
                )
            copied_caps[k] = v

        copied_thresh: dict[str, int] = {}
        for k, v in self.threshold_spend_cents.items():
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(
                    "threshold_spend_cents values must be non-negative integers, "
                    f"got {v!r} for key {k!r}"
                )
            copied_thresh[k] = v

        object.__setattr__(self, "cap_spend_cents", MappingProxyType(copied_caps))
        object.__setattr__(self, "threshold_spend_cents", MappingProxyType(copied_thresh))

    def get_cap_spend(self, cap_group_key: str) -> int:
        """Return prior spend in cents for a cap group in the current period."""
        return self.cap_spend_cents.get(cap_group_key, 0)

    def get_threshold_spend(self, threshold_key: str) -> int:
        """Return prior spend in cents for a threshold period."""
        return self.threshold_spend_cents.get(threshold_key, 0)


@dataclass(frozen=True, slots=True)
class Valuation:
    """Estimated valuation in cents per reward unit."""

    reward_currency: str
    cents_per_unit: Decimal
    is_user_set: bool = False

    def __post_init__(self) -> None:
        _validate_decimal(self.cents_per_unit, "cents_per_unit", allow_zero=False)


@dataclass(frozen=True, slots=True)
class CardContext:
    """Complete rule and cap configuration for a single card."""

    card_id: int
    card_name: str
    reward_currency: str
    rules: Sequence[EarningRule]
    caps: Sequence[SpendCap] = ()

    def __post_init__(self) -> None:
        # Enforce deep immutability and sequence determinism
        object.__setattr__(self, "rules", _normalize_sequence(self.rules, "rules"))
        object.__setattr__(self, "caps", _normalize_sequence(self.caps, "caps"))


@dataclass(frozen=True, slots=True)
class AppliedPortion:
    """Portion of a purchase amount evaluated under a specific rule."""

    portion_cents: int
    rule_id: int
    rule_key: str
    rule_version: int
    multiplier: Decimal
    reward_units: Decimal
    cap_group_key: str | None = None

    def __post_init__(self) -> None:
        _validate_cents(self.portion_cents, "portion_cents")
        _validate_decimal(self.multiplier, "multiplier", allow_zero=True)
        _validate_decimal(self.reward_units, "reward_units", allow_zero=True)


@dataclass(frozen=True, slots=True)
class TraceStep:
    """A discrete, structured evaluation step recorded during calculation."""

    step_number: int
    step_type: str
    action: str
    detail: str
    rule_id: int | None = None
    rule_key: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CardEvaluation:
    """The pure calculation and explanation result for a single card."""

    card_id: int
    card_name: str
    reward_currency: str
    status: CardStatus
    reward_units: Decimal
    estimated_value_cents: int | None = None
    valuation_used: Valuation | None = None
    applied_portions: Sequence[AppliedPortion] = ()
    trace: Sequence[TraceStep] = ()
    explanation: Sequence[str] = ()
    warnings: Sequence[str] = ()
    rejection_reason: str | None = None
    rejection_message: str | None = None

    def __post_init__(self) -> None:
        _validate_decimal(self.reward_units, "reward_units", allow_zero=True)

        if self.estimated_value_cents is not None and (
            not isinstance(self.estimated_value_cents, int)
            or isinstance(self.estimated_value_cents, bool)
            or self.estimated_value_cents < 0
        ):
            raise ValueError("estimated_value_cents must be a non-negative integer")

        if self.status == CardStatus.RANKED:
            if self.estimated_value_cents is None:
                raise ValueError("Ranked evaluation must have estimated_value_cents")
            if self.rejection_reason is not None:
                raise ValueError("Ranked evaluation cannot have rejection_reason")

        elif self.status == CardStatus.UNRANKED:
            if self.estimated_value_cents is not None:
                raise ValueError("Unranked evaluation cannot have estimated_value_cents")
            if self.rejection_reason is None:
                raise ValueError("Unranked evaluation must specify a rejection_reason")
            if self.rejection_reason != UnrankedReason.NO_VALUATION.value:
                raise ValueError(
                    "Unranked evaluation rejection_reason must be "
                    f"{UnrankedReason.NO_VALUATION.value}"
                )

        elif self.status == CardStatus.INELIGIBLE:
            if self.reward_units != Decimal("0"):
                raise ValueError("Ineligible evaluation must have 0 reward units")
            if self.estimated_value_cents is not None:
                raise ValueError("Ineligible evaluation cannot have estimated_value_cents")
            if self.rejection_reason is None:
                raise ValueError("Ineligible evaluation must specify a rejection_reason")
            valid_reasons = {r.value for r in IneligibleReason}
            if self.rejection_reason not in valid_reasons:
                raise ValueError(
                    f"Ineligible evaluation rejection_reason must be one of {sorted(valid_reasons)}"
                )

        # Enforce deep immutability and sequence determinism
        object.__setattr__(
            self,
            "applied_portions",
            _normalize_sequence(self.applied_portions, "applied_portions"),
        )
        object.__setattr__(self, "trace", _normalize_sequence(self.trace, "trace"))
        object.__setattr__(
            self,
            "explanation",
            _normalize_sequence(self.explanation, "explanation"),
        )
        object.__setattr__(self, "warnings", _normalize_sequence(self.warnings, "warnings"))
