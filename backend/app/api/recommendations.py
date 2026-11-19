"""API routes for profiles, categories, and purchase recommendations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import Settings, get_settings
from app.schemas.recommendations import (
    CategorySummary,
    ProfileResetResponse,
    ProfileSummary,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendations import (
    list_categories,
    list_profiles,
    recommend_for_profile,
    reset_profile,
)

router = APIRouter(tags=["recommendations"])


@router.get("/profiles", response_model=list[ProfileSummary])
async def get_profiles(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ProfileSummary]:
    """List available demo/user profiles."""
    return await list_profiles(session)


@router.get("/categories", response_model=list[CategorySummary])
async def get_categories(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CategorySummary]:
    """List spending categories."""
    return await list_categories(session)


@router.post("/profiles/{profile_key}/reset", response_model=ProfileResetResponse)
async def post_profile_reset(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileResetResponse:
    """Reset a demo profile and its associated state back to seeded defaults."""
    return await reset_profile(session, profile_key)


@router.post("/profiles/{profile_key}/recommendations", response_model=RecommendationResponse)
async def post_recommendations(
    profile_key: str,
    payload: RecommendationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecommendationResponse:
    """Evaluate all active cards for a profile and return ranked recommendations."""
    return await recommend_for_profile(session, profile_key, payload, settings)
