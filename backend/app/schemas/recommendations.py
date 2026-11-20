"""Pydantic schemas for profiles, categories, and purchase recommendations."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, StrictInt, field_validator


class ProfileSummary(BaseModel):
    """Public summary of a demo or user profile."""

    id: int
    slug: str
    display_name: str
    is_demo: bool


class ProfileResetResponse(BaseModel):
    """Response returned after resetting a demo profile to its seeded baseline."""

    status: str = "reset"
    profile: ProfileSummary
    cards_restored: int
    valuations_restored: int


class CategorySummary(BaseModel):
    """Spending category metadata."""

    id: int
    code: str
    name: str


class RecommendationRequest(BaseModel):
    """Input payload for comparing cards on a purchase."""

    amount_cents: int = Field(..., gt=0, description="Purchase amount in integer USD cents.")
    category_code: str = Field(..., min_length=1, max_length=64)
    merchant_id: int | None = None
    purchase_date: date | None = None
    card_ids: list[StrictInt] | None = Field(
        default=None,
        description="Optional subset of profile card IDs to evaluate.",
    )

    @field_validator("card_ids")
    @classmethod
    def _validate_card_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if len(value) == 0:
            raise ValueError("card_ids must not be empty when provided.")
        if any(cid <= 0 for cid in value):
            raise ValueError("card_ids must contain only positive integers.")
        if len(set(value)) != len(value):
            raise ValueError("card_ids must not contain duplicate card IDs.")
        return value


class AppliedPortionSchema(BaseModel):
    """Portion of a purchase evaluated under a specific earning rule."""

    portion_cents: int
    rule_id: int
    rule_key: str
    rule_version: int
    multiplier: str
    reward_units: str


class CardRecommendationItem(BaseModel):
    """Single card evaluation outcome in a recommendation response."""

    rank: int | None = None
    profile_card_id: int
    card_name: str
    reward_currency: str
    status: str
    reward_units: str
    estimated_value_cents: int | None = None
    reason: str | None = None
    message: str | None = None
    applied: list[AppliedPortionSchema]
    explanation: list[str]
    warnings: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    """Ranked, unranked, and ineligible cards for a purchase."""

    ranked: list[CardRecommendationItem]
    unranked: list[CardRecommendationItem]
    ineligible: list[CardRecommendationItem]
    global_notes: list[str]
    engine_version: str = "1.0.0"
