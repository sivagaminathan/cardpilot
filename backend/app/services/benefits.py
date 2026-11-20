"""Service layer for benefit period math, status evaluation, and usage CRUD (T33, AC-11)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine import Period, PeriodBounds, get_period_bounds
from app.models import BenefitDefinition, BenefitUsage, ProfileCard
from app.schemas.benefits import (
    BenefitStatusItem,
    BenefitUsageCreate,
    BenefitUsageSummary,
)
from app.seeds.loader import ensure_seeded
from app.services.catalog import resolve_profile


def get_benefit_period_bounds(
    reset_period: str,
    target_date: date,
    opened_on: date | None = None,
) -> PeriodBounds:
    """Compute inclusive period bounds and next reset date for a benefit reset_period."""
    if reset_period == "semiannual":
        if target_date.month <= 6:
            start_date = date(target_date.year, 1, 1)
            end_date = date(target_date.year, 6, 30)
        else:
            start_date = date(target_date.year, 7, 1)
            end_date = date(target_date.year, 12, 31)
        return PeriodBounds(
            start_date=start_date,
            end_date=end_date,
            next_reset_date=end_date + timedelta(days=1),
        )

    try:
        engine_period = Period(reset_period)
    except ValueError as exc:
        raise ValueError(f"Unsupported benefit reset_period: {reset_period!r}") from exc

    return get_period_bounds(engine_period, target_date, opened_on=opened_on)


def _to_usage_summary(usage: BenefitUsage) -> BenefitUsageSummary:
    return BenefitUsageSummary(
        id=usage.id,
        profile_card_id=usage.profile_card_id,
        benefit_definition_id=usage.benefit_definition_id,
        amount_cents=usage.amount_cents,
        used_on=usage.used_on,
        note=usage.note,
    )


async def list_profile_benefits(
    session: AsyncSession,
    profile_key: str,
    *,
    as_of_date: date,
) -> list[BenefitStatusItem]:
    """Evaluate all effective benefits and current-period usages for a profile's active cards."""
    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    profile_cards = (
        await session.scalars(
            select(ProfileCard)
            .where(ProfileCard.profile_id == profile.id, ProfileCard.is_active.is_(True))
            .options(selectinload(ProfileCard.card_product))
            .order_by(ProfileCard.id)
        )
    ).all()
    if not profile_cards:
        return []

    product_ids = sorted({pc.card_product_id for pc in profile_cards})
    benefits = (
        await session.scalars(
            select(BenefitDefinition)
            .where(
                BenefitDefinition.card_product_id.in_(product_ids),
                BenefitDefinition.effective_from <= as_of_date,
                (
                    BenefitDefinition.effective_to.is_(None)
                    | (BenefitDefinition.effective_to >= as_of_date)
                ),
            )
            .order_by(BenefitDefinition.id)
        )
    ).all()
    if not benefits:
        return []

    benefits_by_product: dict[int, list[BenefitDefinition]] = {}
    for benefit in benefits:
        benefits_by_product.setdefault(benefit.card_product_id, []).append(benefit)

    card_ids = [pc.id for pc in profile_cards]
    benefit_ids = [b.id for b in benefits]
    all_usages = (
        await session.scalars(
            select(BenefitUsage)
            .where(
                BenefitUsage.profile_card_id.in_(card_ids),
                BenefitUsage.benefit_definition_id.in_(benefit_ids),
            )
            .order_by(BenefitUsage.used_on.desc(), BenefitUsage.id.desc())
        )
    ).all()

    usages_by_pair: dict[tuple[int, int], list[BenefitUsage]] = {}
    for usage in all_usages:
        usages_by_pair.setdefault((usage.profile_card_id, usage.benefit_definition_id), []).append(
            usage
        )

    items: list[BenefitStatusItem] = []
    for pc in profile_cards:
        product = pc.card_product
        for benefit in benefits_by_product.get(pc.card_product_id, ()):
            bounds: PeriodBounds | None
            if benefit.reset_period == "card_year" and (
                pc.opened_on is None or as_of_date < pc.opened_on
            ):
                bounds = None
            else:
                bounds = get_benefit_period_bounds(
                    benefit.reset_period,
                    as_of_date,
                    opened_on=pc.opened_on,
                )

            pair_usages = usages_by_pair.get((pc.id, benefit.id), ())
            period_usages = (
                [u for u in pair_usages if bounds.start_date <= u.used_on <= bounds.end_date]
                if bounds is not None
                else []
            )

            if benefit.value_cents is not None:
                used_cents: int | None = sum(u.amount_cents or 0 for u in period_usages)
                assert used_cents is not None
                remaining_cents: int | None = max(0, benefit.value_cents - used_cents)
                over_used_cents: int | None = max(0, used_cents - benefit.value_cents)
                is_over_used = used_cents > benefit.value_cents
                if is_over_used:
                    benefit_status = "over_used"
                elif used_cents == benefit.value_cents:
                    benefit_status = "used"
                elif used_cents > 0:
                    benefit_status = "partially_used"
                else:
                    benefit_status = "unused"
            else:
                used_cents = None
                remaining_cents = None
                over_used_cents = None
                is_over_used = False
                benefit_status = "used" if period_usages else "unused"

            items.append(
                BenefitStatusItem(
                    benefit_id=benefit.id,
                    profile_card_id=pc.id,
                    card_name=pc.nickname,
                    card_product_id=product.id,
                    card_product_name=product.name,
                    name=benefit.name,
                    benefit_type=benefit.benefit_type,
                    value_cents=benefit.value_cents,
                    reset_period=benefit.reset_period,
                    notes=benefit.notes,
                    period_start=bounds.start_date if bounds is not None else None,
                    period_end=bounds.end_date if bounds is not None else None,
                    next_reset_date=bounds.next_reset_date if bounds is not None else None,
                    days_until_reset=(
                        (bounds.next_reset_date - as_of_date).days if bounds is not None else None
                    ),
                    used_cents=used_cents,
                    remaining_cents=remaining_cents,
                    over_used_cents=over_used_cents,
                    is_over_used=is_over_used,
                    usage_count=len(period_usages),
                    status=benefit_status,
                    usages=[_to_usage_summary(u) for u in period_usages],
                )
            )

    return items


async def create_benefit_usage(
    session: AsyncSession,
    profile_key: str,
    benefit_id: int,
    payload: BenefitUsageCreate,
) -> BenefitUsageSummary:
    """Record a benefit usage entry after validating ownership, product match, and amount."""
    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    profile_card = await session.scalar(
        select(ProfileCard).where(
            ProfileCard.id == payload.profile_card_id,
            ProfileCard.profile_id == profile.id,
        )
    )
    if profile_card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Profile card {payload.profile_card_id} not found for profile '{profile.slug}'."
            ),
        )

    benefit = await session.scalar(
        select(BenefitDefinition).where(BenefitDefinition.id == benefit_id)
    )
    if benefit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benefit {benefit_id} not found.",
        )

    if benefit.card_product_id != profile_card.card_product_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Benefit does not belong to the selected profile card's product.",
        )

    if payload.used_on < benefit.effective_from or (
        benefit.effective_to is not None and payload.used_on > benefit.effective_to
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="used_on is outside the benefit's effective date range.",
        )

    if benefit.value_cents is not None and payload.amount_cents is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="amount_cents is required for monetary benefits.",
        )
    if benefit.value_cents is None and payload.amount_cents is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="amount_cents must be null for non-monetary perk benefits.",
        )

    usage = BenefitUsage(
        profile_card_id=profile_card.id,
        benefit_definition_id=benefit.id,
        amount_cents=payload.amount_cents,
        used_on=payload.used_on,
        note=payload.note,
    )
    session.add(usage)
    await session.commit()
    await session.refresh(usage)
    return _to_usage_summary(usage)


async def delete_benefit_usage(
    session: AsyncSession,
    profile_key: str,
    benefit_id: int,
    usage_id: int,
) -> None:
    """Delete a benefit usage scoped to the target profile and benefit definition."""
    await ensure_seeded(session)
    await session.commit()

    profile = await resolve_profile(session, profile_key)

    usage = await session.scalar(
        select(BenefitUsage)
        .join(ProfileCard, BenefitUsage.profile_card_id == ProfileCard.id)
        .where(
            BenefitUsage.id == usage_id,
            BenefitUsage.benefit_definition_id == benefit_id,
            ProfileCard.profile_id == profile.id,
        )
    )
    if usage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Benefit usage {usage_id} not found for benefit {benefit_id} "
                f"and profile '{profile.slug}'."
            ),
        )

    await session.delete(usage)
    await session.commit()
