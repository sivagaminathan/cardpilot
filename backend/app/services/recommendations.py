"""Service layer assembling DB state for the pure recommendation engine."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.engine import (
    CardContext,
    CardEvaluation,
    ExclusionType,
    Period,
    PostCapBehavior,
    Purchase,
    RoundingMode,
    ScopeType,
    SpendHistory,
    Valuation,
    evaluate_purchase,
    get_period_bounds,
    rank_card_evaluations,
)
from app.engine import (
    EarningRule as EngineRule,
)
from app.engine import (
    RuleExclusion as EngineExclusion,
)
from app.engine import (
    SpendCap as EngineCap,
)
from app.models import (
    CardProduct,
    Category,
    CurrencyValuation,
    Merchant,
    Profile,
    ProfileCard,
    Transaction,
)
from app.models import (
    EarningRule as DbRule,
)
from app.models import (
    SpendCap as DbCap,
)
from app.schemas.recommendations import (
    AppliedPortionSchema,
    CardRecommendationItem,
    CategorySummary,
    ProfileResetResponse,
    ProfileSummary,
    RecommendationRequest,
    RecommendationResponse,
)
from app.seeds.loader import ensure_seeded, reset_profile_to_seed

_logger = logging.getLogger("cardpilot.recommendations")
_tracer = otel_trace.get_tracer("cardpilot.recommendations")


def _record_recommendation_metric(category_code: str, outcome: str) -> None:
    meter = otel_metrics.get_meter("cardpilot.recommendations")
    counter = meter.create_counter(
        name="cardpilot_recommendations",
        description="Total purchase recommendation evaluations",
    )
    counter.add(1, {"category": category_code, "outcome": outcome})


async def list_profiles(session: AsyncSession) -> list[ProfileSummary]:
    """Return all profiles, seeding demo data if the database is empty."""
    await ensure_seeded(session)
    await session.commit()
    rows = (await session.scalars(select(Profile).order_by(Profile.id))).all()
    return [
        ProfileSummary(id=p.id, slug=p.slug, display_name=p.display_name, is_demo=p.is_demo)
        for p in rows
    ]


async def list_categories(session: AsyncSession) -> list[CategorySummary]:
    """Return all spending categories, seeding catalog if empty."""
    await ensure_seeded(session)
    await session.commit()
    rows = (await session.scalars(select(Category).order_by(Category.id))).all()
    return [CategorySummary(id=c.id, code=c.code, name=c.name) for c in rows]


async def reset_profile(session: AsyncSession, profile_key: str) -> ProfileResetResponse:
    """Reset a demo profile to its original seeded state inside a single transaction."""
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

    try:
        cards_restored, valuations_restored = await reset_profile_to_seed(session, profile)
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        await session.rollback()
        raise

    return ProfileResetResponse(
        status="reset",
        profile=ProfileSummary(
            id=profile.id,
            slug=profile.slug,
            display_name=profile.display_name,
            is_demo=profile.is_demo,
        ),
        cards_restored=cards_restored,
        valuations_restored=valuations_restored,
    )


def _to_engine_rule(db_rule: DbRule) -> EngineRule:
    exclusions = tuple(
        EngineExclusion(
            exclusion_type=ExclusionType(ex.exclusion_type),
            target=(
                ex.target_category.code
                if ex.exclusion_type == "category" and ex.target_category is not None
                else ex.target_merchant.name
                if ex.exclusion_type == "merchant" and ex.target_merchant is not None
                else (ex.target_tag or "")
            ),
            reason=ex.reason,
        )
        for ex in db_rule.exclusions
    )
    return EngineRule(
        id=db_rule.id,
        rule_key=db_rule.rule_key,
        version=db_rule.version,
        scope_type=ScopeType(db_rule.scope_type),
        multiplier=Decimal(db_rule.multiplier),
        effective_from=db_rule.effective_from,
        effective_to=db_rule.effective_to,
        category=db_rule.category.code if db_rule.category is not None else None,
        merchant=db_rule.merchant.name if db_rule.merchant is not None else None,
        priority=db_rule.priority,
        cap_group_key=db_rule.cap.cap_group_key if db_rule.cap is not None else None,
        post_cap_behavior=PostCapBehavior(db_rule.post_cap_behavior),
        min_transaction_cents=db_rule.min_transaction_cents,
        min_period_spend_cents=db_rule.min_period_spend_cents,
        threshold_period=Period(db_rule.threshold_period) if db_rule.threshold_period else None,
        rounding=RoundingMode(db_rule.rounding),
        exclusions=exclusions,
        source_id=db_rule.source_id,
        last_reviewed_on=db_rule.last_reviewed_on,
    )


def _to_item(ev: CardEvaluation, rank: int | None = None) -> CardRecommendationItem:
    return CardRecommendationItem(
        rank=rank,
        profile_card_id=ev.card_id,
        card_name=ev.card_name,
        reward_currency=ev.reward_currency,
        status=ev.status.value,
        reward_units=str(ev.reward_units),
        estimated_value_cents=ev.estimated_value_cents,
        reason=ev.rejection_reason,
        message=ev.rejection_message
        or (ev.explanation[0] if ev.status.value != "ranked" and ev.explanation else None),
        applied=[
            AppliedPortionSchema(
                portion_cents=p.portion_cents,
                rule_id=p.rule_id,
                rule_key=p.rule_key,
                rule_version=p.rule_version,
                multiplier=str(p.multiplier),
                reward_units=str(p.reward_units),
            )
            for p in ev.applied_portions
        ],
        explanation=list(ev.explanation),
        warnings=list(ev.warnings),
    )


@dataclass(frozen=True, slots=True)
class AssembledCardInput:
    """Engine inputs assembled from PostgreSQL for one active profile card."""

    card: CardContext
    spend_history: SpendHistory
    valuation: Valuation | None


async def assemble_profile_engine_inputs(
    session: AsyncSession,
    profile_id: int,
    purchase_date: date,
    *,
    card_ids: Sequence[int] | None = None,
    include_inactive: bool = False,
) -> list[AssembledCardInput]:
    """Load profile cards, rules, caps, spend history, and valuations for a profile."""
    card_stmt = (
        select(ProfileCard)
        .where(ProfileCard.profile_id == profile_id)
        .options(selectinload(ProfileCard.card_product).selectinload(CardProduct.reward_currency))
        .order_by(ProfileCard.id)
    )
    if not include_inactive:
        card_stmt = card_stmt.where(ProfileCard.is_active.is_(True))
    if card_ids is not None:
        card_stmt = card_stmt.where(ProfileCard.id.in_(list(card_ids)))

    profile_cards = (await session.scalars(card_stmt)).all()
    valuations_rows = (
        await session.scalars(
            select(CurrencyValuation).where(CurrencyValuation.profile_id == profile_id)
        )
    ).all()
    valuations_by_currency_id = {v.reward_currency_id: v for v in valuations_rows}

    assembled: list[AssembledCardInput] = []
    for pc in profile_cards:
        product = pc.card_product
        currency = product.reward_currency

        db_rules = (
            await session.scalars(
                select(DbRule)
                .where(DbRule.card_product_id == product.id)
                .options(
                    selectinload(DbRule.category),
                    selectinload(DbRule.merchant),
                    selectinload(DbRule.cap),
                    selectinload(DbRule.exclusions).selectinload(
                        DbRule.exclusions.property.mapper.class_.target_category
                    ),
                    selectinload(DbRule.exclusions).selectinload(
                        DbRule.exclusions.property.mapper.class_.target_merchant
                    ),
                )
                .order_by(DbRule.id)
            )
        ).all()

        db_caps = (
            await session.scalars(select(DbCap).where(DbCap.card_product_id == product.id))
        ).all()

        card_txs = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.profile_id == profile_id,
                    Transaction.profile_card_id == pc.id,
                    Transaction.occurred_on <= purchase_date,
                )
            )
        ).all()

        cap_spend: dict[str, int] = {}
        for db_cap in db_caps:
            bounds = get_period_bounds(
                Period(db_cap.period),
                purchase_date,
                opened_on=pc.opened_on,
            )
            cap_spend[db_cap.cap_group_key] = sum(
                tx.amount_cents
                for tx in card_txs
                if bounds.start_date <= tx.occurred_on <= bounds.end_date
            )

        threshold_spend: dict[str, int] = {}
        for db_rule in db_rules:
            if db_rule.threshold_period:
                bounds = get_period_bounds(
                    Period(db_rule.threshold_period),
                    purchase_date,
                    opened_on=pc.opened_on,
                )
                threshold_spend[db_rule.threshold_period] = sum(
                    tx.amount_cents
                    for tx in card_txs
                    if bounds.start_date <= tx.occurred_on <= bounds.end_date
                )

        val_row = valuations_by_currency_id.get(currency.id)
        valuation = (
            Valuation(
                reward_currency=currency.code,
                cents_per_unit=Decimal(val_row.cents_per_unit),
                is_user_set=val_row.is_user_set,
            )
            if val_row is not None
            else None
        )

        ctx = CardContext(
            card_id=pc.id,
            card_name=pc.nickname,
            reward_currency=currency.code,
            rules=tuple(_to_engine_rule(r) for r in db_rules),
            caps=tuple(
                EngineCap(
                    cap_group_key=c.cap_group_key,
                    cap_amount_cents=c.cap_amount_cents,
                    period=Period(c.period),
                )
                for c in db_caps
            ),
        )
        assembled.append(
            AssembledCardInput(
                card=ctx,
                spend_history=SpendHistory(
                    cap_spend_cents=cap_spend,
                    threshold_spend_cents=threshold_spend,
                ),
                valuation=valuation,
            )
        )

    return assembled


async def recommend_for_profile(
    session: AsyncSession,
    profile_key: str,
    request: RecommendationRequest,
    settings: Settings,
) -> RecommendationResponse:
    """Evaluate all active cards for a profile and return ranked recommendations."""
    with _tracer.start_as_current_span("cardpilot.recommend") as span:
        span.set_attribute("cardpilot.profile_key", profile_key)
        span.set_attribute("cardpilot.category_code", request.category_code)

        if settings.is_dev_fault_injection_active:
            _record_recommendation_metric(request.category_code, "fault_injected")
            _logger.error(
                "recommendation.fault_injected",
                extra={"path": "/api/v1/profiles/{profile_key}/recommendations"},
            )
            raise RuntimeError(
                "Simulated development fault: recommendation engine dependency unavailable"
            )

        await ensure_seeded(session)
        await session.commit()

        if profile_key.isdigit():
            profile = await session.scalar(select(Profile).where(Profile.id == int(profile_key)))
        else:
            profile = await session.scalar(select(Profile).where(Profile.slug == profile_key))

        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{profile_key}' not found.",
            )

        category = await session.scalar(
            select(Category).where(Category.code == request.category_code)
        )
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown category '{request.category_code}'.",
            )

        merchant_name: str | None = None
        merchant_tags: tuple[str, ...] = ()
        if request.merchant_id is not None:
            merchant = await session.scalar(
                select(Merchant).where(Merchant.id == request.merchant_id)
            )
            if merchant is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown merchant_id {request.merchant_id}.",
                )
            merchant_name = merchant.name
            merchant_tags = tuple(merchant.tags)

        purchase_date = request.purchase_date or date.today()
        purchase = Purchase(
            amount_cents=request.amount_cents,
            category=category.code,
            purchase_date=purchase_date,
            merchant=merchant_name,
            merchant_tags=merchant_tags,
        )

        assembled = await assemble_profile_engine_inputs(
            session,
            profile.id,
            purchase_date,
            card_ids=request.card_ids,
        )
        if request.card_ids is not None:
            found_ids = {item.card.card_id for item in assembled}
            missing_ids = [cid for cid in request.card_ids if cid not in found_ids]
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Profile card(s) {missing_ids} not found or inactive "
                        f"for profile '{profile.slug}'."
                    ),
                )
        evaluations: list[CardEvaluation] = [
            evaluate_purchase(
                purchase=purchase,
                card=item.card,
                spend_history=item.spend_history,
                valuation=item.valuation,
            )
            for item in assembled
        ]

        ranked_res = rank_card_evaluations(evaluations)
        span.set_attribute("cardpilot.cards_evaluated", len(evaluations))
        _record_recommendation_metric(request.category_code, "success")
        _logger.info(
            "recommendation.completed",
            extra={"path": "/api/v1/profiles/{profile_key}/recommendations"},
        )

        return RecommendationResponse(
            ranked=[_to_item(ev, rank=idx) for idx, ev in enumerate(ranked_res.ranked, start=1)],
            unranked=[_to_item(ev) for ev in ranked_res.unranked],
            ineligible=[_to_item(ev) for ev in ranked_res.ineligible],
            global_notes=list(ranked_res.global_notes),
        )
