"""Service layer for per-currency rewards summary aggregation (T34, AC-10, FR-27, FR-29)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import Valuation, evaluate_valuation
from app.models import CurrencyValuation, RewardCurrency, Transaction, TransactionRewardCalc
from app.schemas.rewards import CurrencyRewardSummary, RewardsSummaryResponse
from app.seeds.loader import ensure_seeded
from app.services.catalog import resolve_profile

_ESTIMATED_TOTAL_LABEL = (
    "Estimated USD value based on current valuations (excludes unvalued currencies)"
)


async def get_rewards_summary(
    session: AsyncSession,
    profile_key: str,
) -> RewardsSummaryResponse:
    """Aggregate stored transaction snapshots per currency and value with current valuations."""
    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    agg_stmt = (
        select(
            RewardCurrency.id,
            RewardCurrency.code,
            RewardCurrency.name,
            RewardCurrency.kind,
            func.sum(TransactionRewardCalc.reward_units).label("total_units"),
            func.count(TransactionRewardCalc.id).label("tx_count"),
        )
        .join(
            TransactionRewardCalc,
            TransactionRewardCalc.reward_currency_id == RewardCurrency.id,
        )
        .join(Transaction, TransactionRewardCalc.transaction_id == Transaction.id)
        .where(Transaction.profile_id == profile.id)
        .group_by(
            RewardCurrency.id,
            RewardCurrency.code,
            RewardCurrency.name,
            RewardCurrency.kind,
        )
        .order_by(RewardCurrency.id)
    )
    rows = (await session.execute(agg_stmt)).all()

    valuations = (
        await session.scalars(
            select(CurrencyValuation).where(CurrencyValuation.profile_id == profile.id)
        )
    ).all()
    valuations_by_currency_id = {v.reward_currency_id: v for v in valuations}

    currencies: list[CurrencyRewardSummary] = []
    estimated_total_usd_cents = 0
    excluded_unvalued_codes: list[str] = []

    for row in rows:
        total_units = Decimal(row.total_units)
        val_row = valuations_by_currency_id.get(row.id)
        valuation = (
            Valuation(
                reward_currency=row.code,
                cents_per_unit=Decimal(val_row.cents_per_unit),
                is_user_set=val_row.is_user_set,
            )
            if val_row is not None
            else None
        )
        val_result = evaluate_valuation(
            reward_units=total_units,
            reward_currency=row.code,
            valuation=valuation,
        )

        if val_result.estimated_value_cents is not None and val_row is not None:
            estimated_total_usd_cents += val_result.estimated_value_cents
            is_valued = True
            valuation_status = "valued"
            current_cents_per_unit: str | None = str(val_row.cents_per_unit)
            is_user_set: bool | None = val_row.is_user_set
            limitation_note: str | None = None
        else:
            excluded_unvalued_codes.append(row.code)
            is_valued = False
            valuation_status = "unvalued"
            current_cents_per_unit = None
            is_user_set = None
            limitation_note = val_result.rejection_message

        currencies.append(
            CurrencyRewardSummary(
                reward_currency_id=row.id,
                reward_currency_code=row.code,
                reward_currency_name=row.name,
                reward_currency_kind=row.kind,
                total_reward_units=str(total_units),
                transaction_count=int(row.tx_count),
                is_valued=is_valued,
                valuation_status=valuation_status,
                current_cents_per_unit=current_cents_per_unit,
                is_user_set=is_user_set,
                estimated_value_cents=val_result.estimated_value_cents,
                limitation_note=limitation_note,
            )
        )

    limitation_message = (
        f"Excluded unvalued currencies from estimated USD total: "
        f"{', '.join(excluded_unvalued_codes)}."
        if excluded_unvalued_codes
        else None
    )

    return RewardsSummaryResponse(
        profile_id=profile.id,
        profile_slug=profile.slug,
        currencies=currencies,
        estimated_total_usd_cents=estimated_total_usd_cents,
        estimated_total_label=_ESTIMATED_TOTAL_LABEL,
        excluded_unvalued_currency_codes=excluded_unvalued_codes,
        limitation_message=limitation_message,
    )
