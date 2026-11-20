"""API routes for benefit status and usage tracking (T33, AC-11)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.benefits import (
    BenefitStatusItem,
    BenefitUsageCreate,
    BenefitUsageSummary,
)
from app.services.benefits import (
    create_benefit_usage,
    delete_benefit_usage,
    list_profile_benefits,
)

router = APIRouter(tags=["benefits"])


@router.get("/profiles/{profile_key}/benefits", response_model=list[BenefitStatusItem])
async def get_profile_benefits(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_of_date: date | None = None,
) -> list[BenefitStatusItem]:
    """Return current-period benefit status for all active cards in a profile."""
    return await list_profile_benefits(
        session,
        profile_key,
        as_of_date=as_of_date or date.today(),
    )


@router.post(
    "/profiles/{profile_key}/benefits/{benefit_id}/usages",
    response_model=BenefitUsageSummary,
    status_code=status.HTTP_201_CREATED,
)
async def post_benefit_usage(
    profile_key: str,
    benefit_id: int,
    payload: BenefitUsageCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BenefitUsageSummary:
    """Log a benefit usage entry for a profile card."""
    return await create_benefit_usage(session, profile_key, benefit_id, payload)


@router.delete(
    "/profiles/{profile_key}/benefits/{benefit_id}/usages/{usage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_benefit_usage_route(
    profile_key: str,
    benefit_id: int,
    usage_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Delete a logged benefit usage entry."""
    await delete_benefit_usage(session, profile_key, benefit_id, usage_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
