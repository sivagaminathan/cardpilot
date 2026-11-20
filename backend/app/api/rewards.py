"""API route for per-currency rewards summary (T34, AC-10)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.rewards import RewardsSummaryResponse
from app.services.rewards import get_rewards_summary

router = APIRouter(tags=["rewards"])


@router.get("/profiles/{profile_key}/rewards/summary", response_model=RewardsSummaryResponse)
async def get_profile_rewards_summary(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RewardsSummaryResponse:
    """Return accumulated reward units per currency and a separate estimated USD total."""
    return await get_rewards_summary(session, profile_key)
