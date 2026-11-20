"""Service layer for reference catalog, profile lookup, and profile card CRUD."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    BenefitDefinition,
    CardProduct,
    EarningRule,
    Merchant,
    Profile,
    ProfileCard,
    RewardCurrency,
    RuleExclusion,
)
from app.schemas.catalog import (
    BenefitDefinitionSummary,
    CardProductSummary,
    EarningRuleSummary,
    MerchantSummary,
    ProfileCardCreate,
    ProfileCardSummary,
    ProfileCardUpdate,
    RewardCurrencySummary,
    RuleExclusionSummary,
    RuleSourceSummary,
    SpendCapSummary,
)
from app.schemas.recommendations import ProfileSummary
from app.seeds.loader import ensure_seeded

_PROFILE_CARD_UNIQUE_CONSTRAINT = "uq_profile_cards_profile_product_nickname"


def _is_duplicate_profile_card_error(exc: IntegrityError) -> bool:
    """Return True only when IntegrityError is caused by the profile_cards unique constraint."""
    orig = exc.orig
    constraint_name = getattr(orig, "constraint_name", None)
    if constraint_name is None and orig is not None:
        constraint_name = getattr(orig.__cause__, "constraint_name", None)
    if constraint_name == _PROFILE_CARD_UNIQUE_CONSTRAINT:
        return True
    return _PROFILE_CARD_UNIQUE_CONSTRAINT in str(exc)


def _to_currency_summary(currency: RewardCurrency) -> RewardCurrencySummary:
    return RewardCurrencySummary(
        id=currency.id,
        code=currency.code,
        name=currency.name,
        kind=currency.kind,
        is_cash_equivalent=currency.is_cash_equivalent,
        default_cents_per_unit=str(currency.default_cents_per_unit),
    )


def _to_card_product_summary(product: CardProduct) -> CardProductSummary:
    return CardProductSummary(
        id=product.id,
        issuer_name=product.issuer_name,
        name=product.name,
        annual_fee_cents=product.annual_fee_cents,
        network_label=product.network_label,
        description=product.description,
        reward_currency=_to_currency_summary(product.reward_currency),
    )


def _to_profile_card_summary(card: ProfileCard) -> ProfileCardSummary:
    return ProfileCardSummary(
        id=card.id,
        profile_id=card.profile_id,
        card_product_id=card.card_product_id,
        nickname=card.nickname,
        opened_on=card.opened_on,
        is_active=card.is_active,
        card_product=_to_card_product_summary(card.card_product),
    )


async def resolve_profile(session: AsyncSession, profile_key: str) -> Profile:
    """Resolve a profile by integer ID or slug, seeding if the DB is empty."""
    await ensure_seeded(session)
    if profile_key.isdigit():
        profile = await session.scalar(select(Profile).where(Profile.id == int(profile_key)))
    else:
        profile = await session.scalar(select(Profile).where(Profile.slug == profile_key))

    if profile is None:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_key}' not found.",
        )
    return profile


async def get_profile(session: AsyncSession, profile_key: str) -> ProfileSummary:
    """Return a single profile summary by ID or slug."""
    profile = await resolve_profile(session, profile_key)
    await session.commit()
    return ProfileSummary(
        id=profile.id,
        slug=profile.slug,
        display_name=profile.display_name,
        is_demo=profile.is_demo,
    )


async def list_merchants(session: AsyncSession) -> list[MerchantSummary]:
    """Return all seeded merchants ordered by ID."""
    await ensure_seeded(session)
    await session.commit()
    rows = (
        await session.scalars(
            select(Merchant).options(selectinload(Merchant.default_category)).order_by(Merchant.id)
        )
    ).all()
    return [
        MerchantSummary(
            id=m.id,
            name=m.name,
            default_category_id=m.default_category_id,
            default_category_code=m.default_category.code if m.default_category else None,
            tags=list(m.tags),
        )
        for m in rows
    ]


async def list_reward_currencies(session: AsyncSession) -> list[RewardCurrencySummary]:
    """Return all reward currencies ordered by ID."""
    await ensure_seeded(session)
    await session.commit()
    rows = (await session.scalars(select(RewardCurrency).order_by(RewardCurrency.id))).all()
    return [_to_currency_summary(c) for c in rows]


async def list_card_products(session: AsyncSession) -> list[CardProductSummary]:
    """Return all fictional card products in the catalog."""
    await ensure_seeded(session)
    await session.commit()
    rows = (
        await session.scalars(
            select(CardProduct)
            .options(selectinload(CardProduct.reward_currency))
            .order_by(CardProduct.id)
        )
    ).all()
    return [_to_card_product_summary(p) for p in rows]


async def _require_card_product(session: AsyncSession, card_product_id: int) -> CardProduct:
    await ensure_seeded(session)
    product = await session.scalar(
        select(CardProduct)
        .where(CardProduct.id == card_product_id)
        .options(selectinload(CardProduct.reward_currency))
    )
    if product is None:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card product {card_product_id} not found.",
        )
    return product


async def list_card_product_rules(
    session: AsyncSession, card_product_id: int
) -> list[EarningRuleSummary]:
    """Return earning rules with source metadata and exclusions for a card product."""
    await _require_card_product(session, card_product_id)
    rules = (
        await session.scalars(
            select(EarningRule)
            .where(EarningRule.card_product_id == card_product_id)
            .options(
                selectinload(EarningRule.category),
                selectinload(EarningRule.merchant),
                selectinload(EarningRule.cap),
                selectinload(EarningRule.source),
                selectinload(EarningRule.exclusions).selectinload(RuleExclusion.target_category),
                selectinload(EarningRule.exclusions).selectinload(RuleExclusion.target_merchant),
            )
            .order_by(EarningRule.id)
        )
    ).all()
    await session.commit()
    return [
        EarningRuleSummary(
            id=r.id,
            rule_key=r.rule_key,
            version=r.version,
            scope_type=r.scope_type,
            category_code=r.category.code if r.category else None,
            merchant_name=r.merchant.name if r.merchant else None,
            multiplier=str(r.multiplier),
            priority=r.priority,
            cap=(
                SpendCapSummary(
                    id=r.cap.id,
                    cap_group_key=r.cap.cap_group_key,
                    cap_amount_cents=r.cap.cap_amount_cents,
                    period=r.cap.period,
                )
                if r.cap
                else None
            ),
            post_cap_behavior=r.post_cap_behavior,
            min_transaction_cents=r.min_transaction_cents,
            min_period_spend_cents=r.min_period_spend_cents,
            threshold_period=r.threshold_period,
            rounding=r.rounding,
            effective_from=r.effective_from,
            effective_to=r.effective_to,
            source=RuleSourceSummary(
                id=r.source.id,
                title=r.source.title,
                kind=r.source.kind,
                url=r.source.url,
                notes=r.source.notes,
                last_reviewed_on=r.source.last_reviewed_on,
            ),
            exclusions=[
                RuleExclusionSummary(
                    id=ex.id,
                    exclusion_type=ex.exclusion_type,
                    target_category_code=ex.target_category.code if ex.target_category else None,
                    target_merchant_name=ex.target_merchant.name if ex.target_merchant else None,
                    target_tag=ex.target_tag,
                    reason=ex.reason,
                )
                for ex in r.exclusions
            ],
        )
        for r in rules
    ]


async def list_card_product_benefits(
    session: AsyncSession, card_product_id: int
) -> list[BenefitDefinitionSummary]:
    """Return benefit definitions with source metadata for a card product."""
    await _require_card_product(session, card_product_id)
    benefits = (
        await session.scalars(
            select(BenefitDefinition)
            .where(BenefitDefinition.card_product_id == card_product_id)
            .options(selectinload(BenefitDefinition.source))
            .order_by(BenefitDefinition.id)
        )
    ).all()
    await session.commit()
    return [
        BenefitDefinitionSummary(
            id=b.id,
            name=b.name,
            benefit_type=b.benefit_type,
            value_cents=b.value_cents,
            reset_period=b.reset_period,
            notes=b.notes,
            effective_from=b.effective_from,
            effective_to=b.effective_to,
            source=RuleSourceSummary(
                id=b.source.id,
                title=b.source.title,
                kind=b.source.kind,
                url=b.source.url,
                notes=b.source.notes,
                last_reviewed_on=b.source.last_reviewed_on,
            ),
        )
        for b in benefits
    ]


async def list_profile_cards(session: AsyncSession, profile_key: str) -> list[ProfileCardSummary]:
    """Return all cards belonging to the specified profile."""
    profile = await resolve_profile(session, profile_key)
    cards = (
        await session.scalars(
            select(ProfileCard)
            .where(ProfileCard.profile_id == profile.id)
            .options(
                selectinload(ProfileCard.card_product).selectinload(CardProduct.reward_currency)
            )
            .order_by(ProfileCard.id)
        )
    ).all()
    await session.commit()
    return [_to_profile_card_summary(c) for c in cards]


async def add_profile_card(
    session: AsyncSession, profile_key: str, payload: ProfileCardCreate
) -> ProfileCardSummary:
    """Add a card from the catalog to the specified profile."""
    profile = await resolve_profile(session, profile_key)
    product = await _require_card_product(session, payload.card_product_id)
    nickname = payload.nickname.strip()
    if not nickname:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Card nickname must not be blank.",
        )

    duplicate = await session.scalar(
        select(ProfileCard).where(
            ProfileCard.profile_id == profile.id,
            ProfileCard.card_product_id == product.id,
            ProfileCard.nickname == nickname,
        )
    )
    if duplicate is not None:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Profile already holds '{nickname}' for this card product.",
        )

    card = ProfileCard(
        profile_id=profile.id,
        card_product_id=product.id,
        nickname=nickname,
        opened_on=payload.opened_on,
        is_active=payload.is_active,
    )
    session.add(card)
    try:
        await session.flush()
        card_id = card.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _is_duplicate_profile_card_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Profile already holds '{nickname}' for this card product.",
            ) from exc
        raise

    created = await session.scalar(
        select(ProfileCard)
        .where(ProfileCard.id == card_id)
        .options(selectinload(ProfileCard.card_product).selectinload(CardProduct.reward_currency))
    )
    assert created is not None
    return _to_profile_card_summary(created)


async def update_profile_card(
    session: AsyncSession,
    profile_key: str,
    card_id: int,
    payload: ProfileCardUpdate,
) -> ProfileCardSummary:
    """Update a card belonging to the specified profile."""
    profile = await resolve_profile(session, profile_key)
    profile_slug = profile.slug
    card = await session.scalar(
        select(ProfileCard)
        .where(ProfileCard.id == card_id, ProfileCard.profile_id == profile.id)
        .options(selectinload(ProfileCard.card_product).selectinload(CardProduct.reward_currency))
    )
    if card is None:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card {card_id} not found for profile '{profile_slug}'.",
        )

    if payload.nickname is not None:
        cleaned = payload.nickname.strip()
        if not cleaned:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Card nickname must not be blank.",
            )
        duplicate = await session.scalar(
            select(ProfileCard).where(
                ProfileCard.profile_id == profile.id,
                ProfileCard.card_product_id == card.card_product_id,
                ProfileCard.nickname == cleaned,
                ProfileCard.id != card.id,
            )
        )
        if duplicate is not None:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Profile already holds '{cleaned}' for this card product.",
            )
        card.nickname = cleaned

    if "opened_on" in payload.model_fields_set:
        card.opened_on = payload.opened_on
    if payload.is_active is not None:
        card.is_active = payload.is_active

    target_nickname = card.nickname
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _is_duplicate_profile_card_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Profile already holds '{target_nickname}' for this card product.",
            ) from exc
        raise
    await session.refresh(card)
    return _to_profile_card_summary(card)


async def delete_profile_card(session: AsyncSession, profile_key: str, card_id: int) -> None:
    """Remove a card belonging to the specified profile."""
    profile = await resolve_profile(session, profile_key)
    profile_slug = profile.slug
    card = await session.scalar(
        select(ProfileCard).where(ProfileCard.id == card_id, ProfileCard.profile_id == profile.id)
    )
    if card is None:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card {card_id} not found for profile '{profile_slug}'.",
        )
    await session.delete(card)
    await session.commit()
