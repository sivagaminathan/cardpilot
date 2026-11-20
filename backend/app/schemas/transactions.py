"""Pydantic schemas for recorded transactions and immutable reward calculation snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, StrictInt, model_validator

from app.schemas.validators import SafeFreeText


class TransactionCreate(BaseModel):
    """Request payload to record a purchase transaction and persist its reward snapshot."""

    profile_card_id: StrictInt = Field(..., gt=0)
    amount_cents: StrictInt = Field(..., gt=0)
    category_code: str = Field(..., min_length=1, max_length=64)
    merchant_id: StrictInt | None = Field(default=None, gt=0)
    merchant_text: SafeFreeText | None = Field(default=None, min_length=1, max_length=200)
    occurred_on: date
    note: SafeFreeText = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _validate_merchant_exclusivity(self) -> TransactionCreate:
        if self.merchant_id is not None and self.merchant_text is not None:
            raise ValueError("Provide either merchant_id or merchant_text, not both.")
        return self


class TransactionRewardCalcSummary(BaseModel):
    """Immutable calculation snapshot persisted for a transaction."""

    id: int
    engine_version: str
    reward_currency: str
    reward_units: str
    valuation_cents_per_unit_used: str | None = None
    estimated_value_cents: int | None = None
    applied_rule_ids: list[int]
    trace: dict[str, Any]
    created_at: datetime


class TransactionSummary(BaseModel):
    """Recorded transaction with its immutable reward calculation snapshot."""

    id: int
    profile_id: int
    profile_card_id: int
    card_name: str
    amount_cents: int
    category_code: str
    category_name: str
    merchant_id: int | None = None
    merchant_name: str | None = None
    merchant_text: str | None = None
    occurred_on: date
    note: str
    created_at: datetime
    reward_calc: TransactionRewardCalcSummary
