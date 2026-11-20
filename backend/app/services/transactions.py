"""Service layer for recording, listing, and deleting profile transactions (T31)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine import ENGINE_VERSION, CardEvaluation, Purchase, evaluate_purchase
from app.models import (
    CalcRuleReference,
    CardProduct,
    Category,
    Merchant,
    ProfileCard,
    Transaction,
    TransactionRewardCalc,
)
from app.schemas.transactions import (
    TransactionCreate,
    TransactionRewardCalcSummary,
    TransactionSummary,
)
from app.seeds.loader import ensure_seeded
from app.services.catalog import resolve_profile
from app.services.recommendations import assemble_profile_engine_inputs


def _serialize_evaluation_trace(ev: CardEvaluation) -> dict[str, Any]:
    """Serialize a CardEvaluation trace into a JSONB-safe dict with Decimal strings."""
    return {
        "status": ev.status.value,
        "applied_portions": [
            {
                "portion_cents": p.portion_cents,
                "rule_id": p.rule_id,
                "rule_key": p.rule_key,
                "rule_version": p.rule_version,
                "multiplier": str(p.multiplier),
                "reward_units": str(p.reward_units),
                "cap_group_key": p.cap_group_key,
            }
            for p in ev.applied_portions
        ],
        "steps": [
            {
                "step_number": s.step_number,
                "step_type": s.step_type,
                "action": s.action,
                "detail": s.detail,
                "rule_id": s.rule_id,
                "rule_key": s.rule_key,
                "reason": s.reason,
            }
            for s in ev.trace
        ],
        "explanation": list(ev.explanation),
        "warnings": list(ev.warnings),
        "rejection_reason": ev.rejection_reason,
        "rejection_message": ev.rejection_message,
    }


def _to_transaction_summary(tx: Transaction) -> TransactionSummary:
    calc = tx.reward_calc
    if calc is None:  # pragma: no cover - invariant enforced on create
        raise RuntimeError(f"Transaction {tx.id} is missing its reward calculation snapshot.")

    applied_rule_ids = sorted(ref.rule_id for ref in calc.rule_references)
    return TransactionSummary(
        id=tx.id,
        profile_id=tx.profile_id,
        profile_card_id=tx.profile_card_id,
        card_name=tx.profile_card.nickname,
        amount_cents=tx.amount_cents,
        category_code=tx.category.code,
        category_name=tx.category.name,
        merchant_id=tx.merchant_id,
        merchant_name=tx.merchant.name if tx.merchant is not None else None,
        merchant_text=tx.merchant_text,
        occurred_on=tx.occurred_on,
        note=tx.note,
        created_at=tx.created_at,
        reward_calc=TransactionRewardCalcSummary(
            id=calc.id,
            engine_version=calc.engine_version,
            reward_currency=calc.reward_currency.code,
            reward_units=str(calc.reward_units),
            valuation_cents_per_unit_used=(
                str(calc.valuation_cents_per_unit_used)
                if calc.valuation_cents_per_unit_used is not None
                else None
            ),
            estimated_value_cents=calc.estimated_value_cents,
            applied_rule_ids=applied_rule_ids,
            trace=dict(calc.trace),
            created_at=calc.created_at,
        ),
    )


async def list_transactions(
    session: AsyncSession,
    profile_key: str,
    *,
    profile_card_id: int | None = None,
    category_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[TransactionSummary]:
    """List transactions for a profile with optional card, category, and date filters."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must not be after date_to.",
        )

    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    stmt = (
        select(Transaction)
        .where(Transaction.profile_id == profile.id)
        .options(
            selectinload(Transaction.profile_card),
            selectinload(Transaction.category),
            selectinload(Transaction.merchant),
            selectinload(Transaction.reward_calc).selectinload(
                TransactionRewardCalc.reward_currency
            ),
            selectinload(Transaction.reward_calc).selectinload(
                TransactionRewardCalc.rule_references
            ),
        )
        .order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
    )

    if profile_card_id is not None:
        stmt = stmt.where(Transaction.profile_card_id == profile_card_id)
    if category_code is not None:
        stmt = stmt.where(Transaction.category.has(Category.code == category_code))
    if date_from is not None:
        stmt = stmt.where(Transaction.occurred_on >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.occurred_on <= date_to)

    rows = (await session.scalars(stmt)).all()
    return [_to_transaction_summary(tx) for tx in rows]


async def create_transaction(
    session: AsyncSession,
    profile_key: str,
    payload: TransactionCreate,
) -> TransactionSummary:
    """Record a transaction and persist its immutable reward calculation snapshot."""
    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    profile_card = await session.scalar(
        select(ProfileCard)
        .where(
            ProfileCard.id == payload.profile_card_id,
            ProfileCard.profile_id == profile.id,
        )
        .options(
            selectinload(ProfileCard.card_product).selectinload(CardProduct.reward_currency),
        )
    )
    if profile_card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Profile card {payload.profile_card_id} not found for profile '{profile.slug}'."
            ),
        )

    category = await session.scalar(select(Category).where(Category.code == payload.category_code))
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown category '{payload.category_code}'.",
        )

    merchant: Merchant | None = None
    if payload.merchant_id is not None:
        merchant = await session.scalar(select(Merchant).where(Merchant.id == payload.merchant_id))
        if merchant is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown merchant_id {payload.merchant_id}.",
            )

    assembled = await assemble_profile_engine_inputs(
        session,
        profile.id,
        payload.occurred_on,
        card_ids=[profile_card.id],
        include_inactive=True,
    )
    if not assembled:  # pragma: no cover - profile_card existence already verified
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Profile card {payload.profile_card_id} not found for profile '{profile.slug}'."
            ),
        )

    card_input = assembled[0]
    purchase = Purchase(
        amount_cents=payload.amount_cents,
        category=category.code,
        purchase_date=payload.occurred_on,
        merchant=merchant.name if merchant is not None else None,
        merchant_tags=tuple(merchant.tags) if merchant is not None else (),
    )
    ev = evaluate_purchase(
        purchase=purchase,
        card=card_input.card,
        spend_history=card_input.spend_history,
        valuation=card_input.valuation,
    )

    try:
        tx = Transaction(
            profile_id=profile.id,
            profile_card_id=profile_card.id,
            amount_cents=payload.amount_cents,
            category_id=category.id,
            merchant_id=merchant.id if merchant is not None else None,
            merchant_text=payload.merchant_text,
            occurred_on=payload.occurred_on,
            note=payload.note,
        )
        session.add(tx)
        await session.flush()

        trace_payload = _serialize_evaluation_trace(ev)
        calc = TransactionRewardCalc(
            transaction_id=tx.id,
            engine_version=ENGINE_VERSION,
            reward_currency_id=profile_card.card_product.reward_currency_id,
            reward_units=ev.reward_units,
            valuation_cents_per_unit_used=(
                ev.valuation_used.cents_per_unit if ev.valuation_used is not None else None
            ),
            estimated_value_cents=ev.estimated_value_cents,
            trace=trace_payload,
        )
        session.add(calc)
        await session.flush()

        referenced_rule_ids = sorted(
            {p.rule_id for p in ev.applied_portions}
            | {s.rule_id for s in ev.trace if s.rule_id is not None}
        )
        for rule_id in referenced_rule_ids:
            session.add(CalcRuleReference(calc_id=calc.id, rule_id=rule_id))

        await session.commit()
    except Exception:
        await session.rollback()
        raise

    await session.refresh(tx)
    await session.refresh(calc)

    return TransactionSummary(
        id=tx.id,
        profile_id=tx.profile_id,
        profile_card_id=tx.profile_card_id,
        card_name=profile_card.nickname,
        amount_cents=tx.amount_cents,
        category_code=category.code,
        category_name=category.name,
        merchant_id=tx.merchant_id,
        merchant_name=merchant.name if merchant is not None else None,
        merchant_text=tx.merchant_text,
        occurred_on=tx.occurred_on,
        note=tx.note,
        created_at=tx.created_at,
        reward_calc=TransactionRewardCalcSummary(
            id=calc.id,
            engine_version=calc.engine_version,
            reward_currency=profile_card.card_product.reward_currency.code,
            reward_units=str(calc.reward_units),
            valuation_cents_per_unit_used=(
                str(calc.valuation_cents_per_unit_used)
                if calc.valuation_cents_per_unit_used is not None
                else None
            ),
            estimated_value_cents=calc.estimated_value_cents,
            applied_rule_ids=referenced_rule_ids,
            trace=dict(calc.trace),
            created_at=calc.created_at,
        ),
    )


async def delete_transaction(
    session: AsyncSession,
    profile_key: str,
    transaction_id: int,
) -> None:
    """Delete a profile transaction (cascades to snapshot and rule references)."""
    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    tx = await session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.profile_id == profile.id,
        )
    )
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found for profile '{profile.slug}'.",
        )

    await session.delete(tx)
    await session.commit()
