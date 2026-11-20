"""Pydantic schemas for per-currency rewards summary and estimated USD totals (T34, AC-10)."""

from __future__ import annotations

from pydantic import BaseModel


class CurrencyRewardSummary(BaseModel):
    """Accumulated reward units and current valuation estimate for one reward currency."""

    reward_currency_id: int
    reward_currency_code: str
    reward_currency_name: str
    reward_currency_kind: str
    total_reward_units: str
    transaction_count: int
    is_valued: bool
    valuation_status: str
    current_cents_per_unit: str | None = None
    is_user_set: bool | None = None
    estimated_value_cents: int | None = None
    limitation_note: str | None = None


class RewardsSummaryResponse(BaseModel):
    """Per-currency rewards summary with a separately labeled estimated USD total."""

    profile_id: int
    profile_slug: str
    currencies: list[CurrencyRewardSummary]
    estimated_total_usd_cents: int
    estimated_total_label: str
    excluded_unvalued_currency_codes: list[str]
    limitation_message: str | None = None
