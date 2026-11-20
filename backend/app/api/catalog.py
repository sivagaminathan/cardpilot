"""API routes for reference catalog, single profile lookup, and profile cards (T26)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.catalog import (
    BenefitDefinitionSummary,
    CardProductSummary,
    CurrencyValuationSummary,
    CurrencyValuationUpdate,
    EarningRuleSummary,
    MerchantSummary,
    ProfileCardCreate,
    ProfileCardSummary,
    ProfileCardUpdate,
    RewardCurrencySummary,
)
from app.schemas.recommendations import ProfileSummary
from app.services.catalog import (
    add_profile_card,
    delete_profile_card,
    get_profile,
    list_card_product_benefits,
    list_card_product_rules,
    list_card_products,
    list_merchants,
    list_profile_cards,
    list_profile_valuations,
    list_reward_currencies,
    update_profile_card,
    upsert_profile_valuation,
)

router = APIRouter(tags=["catalog"])


@router.get("/merchants", response_model=list[MerchantSummary])
async def get_merchants(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MerchantSummary]:
    """List seeded merchants."""
    return await list_merchants(session)


@router.get("/reward-currencies", response_model=list[RewardCurrencySummary])
async def get_reward_currencies(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RewardCurrencySummary]:
    """List reward currencies."""
    return await list_reward_currencies(session)


@router.get("/card-products", response_model=list[CardProductSummary])
async def get_card_products(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CardProductSummary]:
    """List fictional card products in the catalog."""
    return await list_card_products(session)


@router.get("/card-products/{card_product_id}/rules", response_model=list[EarningRuleSummary])
async def get_card_product_rules(
    card_product_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[EarningRuleSummary]:
    """List earning rules and source metadata for a card product."""
    return await list_card_product_rules(session, card_product_id)


@router.get(
    "/card-products/{card_product_id}/benefits",
    response_model=list[BenefitDefinitionSummary],
)
async def get_card_product_benefits(
    card_product_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[BenefitDefinitionSummary]:
    """List benefit definitions and source metadata for a card product."""
    return await list_card_product_benefits(session, card_product_id)


@router.get("/profiles/{profile_key}", response_model=ProfileSummary)
async def get_profile_by_key(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileSummary:
    """Retrieve a single profile by slug or ID."""
    return await get_profile(session, profile_key)


@router.get("/profiles/{profile_key}/cards", response_model=list[ProfileCardSummary])
async def get_profile_cards(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ProfileCardSummary]:
    """List cards held by a profile."""
    return await list_profile_cards(session, profile_key)


@router.post(
    "/profiles/{profile_key}/cards",
    response_model=ProfileCardSummary,
    status_code=status.HTTP_201_CREATED,
)
async def post_profile_card(
    profile_key: str,
    payload: ProfileCardCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileCardSummary:
    """Add a card from the catalog to a profile."""
    return await add_profile_card(session, profile_key, payload)


@router.patch("/profiles/{profile_key}/cards/{card_id}", response_model=ProfileCardSummary)
async def patch_profile_card(
    profile_key: str,
    card_id: int,
    payload: ProfileCardUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProfileCardSummary:
    """Update a card belonging to a profile."""
    return await update_profile_card(session, profile_key, card_id, payload)


@router.delete(
    "/profiles/{profile_key}/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_profile_card_route(
    profile_key: str,
    card_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Remove a card from a profile."""
    await delete_profile_card(session, profile_key, card_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/profiles/{profile_key}/valuations", response_model=list[CurrencyValuationSummary])
async def get_profile_valuations(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CurrencyValuationSummary]:
    """List currency valuations configured for a profile."""
    return await list_profile_valuations(session, profile_key)


@router.put(
    "/profiles/{profile_key}/valuations/{currency_key}",
    response_model=CurrencyValuationSummary,
)
async def put_profile_valuation(
    profile_key: str,
    currency_key: str,
    payload: CurrencyValuationUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrencyValuationSummary:
    """Create or update a profile's valuation for a reward currency."""
    return await upsert_profile_valuation(session, profile_key, currency_key, payload)
