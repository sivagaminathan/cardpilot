"""Pydantic schemas for benefit status, period tracking, and usage logging (T33, AC-11)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, StrictInt

from app.schemas.validators import SafeFreeText


class BenefitUsageCreate(BaseModel):
    """Request payload to log a usage entry against a card benefit."""

    profile_card_id: StrictInt = Field(..., gt=0)
    amount_cents: StrictInt | None = Field(default=None, gt=0)
    used_on: date
    note: SafeFreeText = Field(default="", max_length=1000)


class BenefitUsageSummary(BaseModel):
    """Persisted benefit usage entry."""

    id: int
    profile_card_id: int
    benefit_definition_id: int
    amount_cents: int | None = None
    used_on: date
    note: str


class BenefitStatusItem(BaseModel):
    """Benefit status for a profile card within the current reset period."""

    benefit_id: int
    profile_card_id: int
    card_name: str
    card_product_id: int
    card_product_name: str
    name: str
    benefit_type: str
    value_cents: int | None = None
    reset_period: str
    notes: str
    period_start: date | None = None
    period_end: date | None = None
    next_reset_date: date | None = None
    days_until_reset: int | None = None
    used_cents: int | None = None
    remaining_cents: int | None = None
    over_used_cents: int | None = None
    is_over_used: bool
    usage_count: int
    status: str
    usages: list[BenefitUsageSummary]
