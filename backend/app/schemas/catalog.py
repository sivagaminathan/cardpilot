"""Pydantic schemas for reference catalog, rules, benefits, profiles, and profile cards."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class RewardCurrencySummary(BaseModel):
    """Reward currency metadata."""

    id: int
    code: str
    name: str
    kind: str
    is_cash_equivalent: bool
    default_cents_per_unit: str


class MerchantSummary(BaseModel):
    """Seeded merchant reference item."""

    id: int
    name: str
    default_category_id: int | None = None
    default_category_code: str | None = None
    tags: list[str]


class CardProductSummary(BaseModel):
    """Fictional card product catalog item."""

    id: int
    issuer_name: str
    name: str
    annual_fee_cents: int
    network_label: str
    description: str
    reward_currency: RewardCurrencySummary


class RuleSourceSummary(BaseModel):
    """Rule or benefit source provenance metadata."""

    id: int
    title: str
    kind: str
    url: str | None = None
    notes: str
    last_reviewed_on: date


class RuleExclusionSummary(BaseModel):
    """Exclusion attached to an earning rule."""

    id: int
    exclusion_type: str
    target_category_code: str | None = None
    target_merchant_name: str | None = None
    target_tag: str | None = None
    reason: str


class SpendCapSummary(BaseModel):
    """Spend cap metadata for an earning rule."""

    id: int
    cap_group_key: str
    cap_amount_cents: int
    period: str


class EarningRuleSummary(BaseModel):
    """Versioned earning rule with source and exclusions."""

    id: int
    rule_key: str
    version: int
    scope_type: str
    category_code: str | None = None
    merchant_name: str | None = None
    multiplier: str
    priority: int
    cap: SpendCapSummary | None = None
    post_cap_behavior: str
    min_transaction_cents: int | None = None
    min_period_spend_cents: int | None = None
    threshold_period: str | None = None
    rounding: str
    effective_from: date
    effective_to: date | None = None
    source: RuleSourceSummary
    exclusions: list[RuleExclusionSummary]


class BenefitDefinitionSummary(BaseModel):
    """Card product benefit definition with source metadata."""

    id: int
    name: str
    benefit_type: str
    value_cents: int | None = None
    reset_period: str
    notes: str
    effective_from: date
    effective_to: date | None = None
    source: RuleSourceSummary


class ProfileCardSummary(BaseModel):
    """Card held within a user or demo profile."""

    id: int
    profile_id: int
    card_product_id: int
    nickname: str
    opened_on: date | None = None
    is_active: bool
    card_product: CardProductSummary


class ProfileCardCreate(BaseModel):
    """Request payload to add a catalog card to a profile."""

    card_product_id: int = Field(..., gt=0)
    nickname: str = Field(..., min_length=1, max_length=128)
    opened_on: date | None = None
    is_active: bool = True


class ProfileCardUpdate(BaseModel):
    """Request payload to update a profile card's nickname, opened date, or active status."""

    nickname: str | None = Field(default=None, min_length=1, max_length=128)
    opened_on: date | None = None
    is_active: bool | None = None


class CurrencyValuationSummary(BaseModel):
    """Per-profile valuation for a reward currency."""

    profile_id: int
    reward_currency_id: int
    reward_currency: RewardCurrencySummary
    cents_per_unit: str
    is_user_set: bool
    updated_at: datetime


class CurrencyValuationUpdate(BaseModel):
    """Request payload to set or update a profile's currency valuation (0 < v <= 10)."""

    cents_per_unit: Decimal = Field(
        ...,
        gt=Decimal("0"),
        le=Decimal("10"),
        description="Estimated USD cents per reward unit (0 < v <= 10).",
    )

    @field_validator("cents_per_unit")
    @classmethod
    def _validate_finite_decimal(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("cents_per_unit must be a finite decimal.")
        quantized = value.quantize(Decimal("0.0001"))
        if quantized <= Decimal("0"):
            raise ValueError("cents_per_unit must be greater than 0 after rounding.")
        return quantized
