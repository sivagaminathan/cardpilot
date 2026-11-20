"""API routes for recording, listing, and deleting profile transactions (T31)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.transactions import TransactionCreate, TransactionSummary
from app.services.transactions import (
    create_transaction,
    delete_transaction,
    list_transactions,
)

router = APIRouter(tags=["transactions"])


@router.get("/profiles/{profile_key}/transactions", response_model=list[TransactionSummary])
async def get_profile_transactions(
    profile_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    profile_card_id: Annotated[int | None, Query(gt=0)] = None,
    category_code: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[TransactionSummary]:
    """List recorded transactions for a profile with optional filters."""
    return await list_transactions(
        session,
        profile_key,
        profile_card_id=profile_card_id,
        category_code=category_code,
        date_from=date_from,
        date_to=date_to,
    )


@router.post(
    "/profiles/{profile_key}/transactions",
    response_model=TransactionSummary,
    status_code=status.HTTP_201_CREATED,
)
async def post_profile_transaction(
    profile_key: str,
    payload: TransactionCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionSummary:
    """Record a transaction and persist an immutable reward calculation snapshot."""
    return await create_transaction(session, profile_key, payload)


@router.delete(
    "/profiles/{profile_key}/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_profile_transaction(
    profile_key: str,
    transaction_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Delete a recorded transaction and its calculation snapshot."""
    await delete_transaction(session, profile_key, transaction_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
