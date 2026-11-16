"""SQLAlchemy 2.0 ORM models for profiles, transactions, calculations, and benefits (T23).

Defines Profile, ProfileCard, CurrencyValuation, Transaction, TransactionRewardCalc,
CalcRuleReference, BenefitDefinition, and BenefitUsage matching ARCHITECTURE.md §2.1-2.3.
Integrates T22's ensure_rule_mutable() with CalcRuleReference lookups.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    exists,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.reference import CardProduct, Category, Merchant, RewardCurrency, RuleSource
from app.models.rules import EarningRule, ensure_rule_mutable


class Profile(Base):
    """User or demo profile scoping cards, valuations, and transactions."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    seed_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    cards: Mapped[list[ProfileCard]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    valuations: Mapped[list[CurrencyValuation]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileCard(Base):
    """A card product held within a profile."""

    __tablename__ = "profile_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_product_id: Mapped[int] = mapped_column(
        ForeignKey("card_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nickname: Mapped[str] = mapped_column(String(128), nullable=False)
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    profile: Mapped[Profile] = relationship(back_populates="cards")
    card_product: Mapped[CardProduct] = relationship()
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="profile_card", cascade="all, delete-orphan"
    )
    benefit_usages: Mapped[list[BenefitUsage]] = relationship(
        back_populates="profile_card", cascade="all, delete-orphan"
    )


class CurrencyValuation(Base):
    """Per-profile cents-per-unit valuation for a reward currency."""

    __tablename__ = "currency_valuations"
    __table_args__ = (
        CheckConstraint("cents_per_unit > 0", name="ck_currency_valuations_cents_per_unit_pos"),
    )

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reward_currency_id: Mapped[int] = mapped_column(
        ForeignKey("reward_currencies.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    cents_per_unit: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    is_user_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile: Mapped[Profile] = relationship(back_populates="valuations")
    reward_currency: Mapped[RewardCurrency] = relationship()


class Transaction(Base):
    """Recorded purchase transaction for a profile card."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_pos"),
        Index("ix_transactions_profile_occurred_on", "profile_id", "occurred_on"),
        Index("ix_transactions_profile_card_occurred_on", "profile_card_id", "occurred_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    profile_card_id: Mapped[int] = mapped_column(
        ForeignKey("profile_cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    merchant_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile: Mapped[Profile] = relationship(back_populates="transactions")
    profile_card: Mapped[ProfileCard] = relationship(back_populates="transactions")
    category: Mapped[Category] = relationship()
    merchant: Mapped[Merchant | None] = relationship()
    reward_calc: Mapped[TransactionRewardCalc | None] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", uselist=False
    )


class TransactionRewardCalc(Base):
    """Immutable calculation snapshot persisted for a transaction."""

    __tablename__ = "transaction_reward_calcs"
    __table_args__ = (
        CheckConstraint("reward_units >= 0", name="ck_transaction_reward_calcs_units_non_neg"),
        CheckConstraint(
            "valuation_cents_per_unit_used IS NULL OR valuation_cents_per_unit_used > 0",
            name="ck_transaction_reward_calcs_valuation_pos",
        ),
        CheckConstraint(
            "estimated_value_cents IS NULL OR estimated_value_cents >= 0",
            name="ck_transaction_reward_calcs_est_value_non_neg",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    reward_currency_id: Mapped[int] = mapped_column(
        ForeignKey("reward_currencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reward_units: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valuation_cents_per_unit_used: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    estimated_value_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transaction: Mapped[Transaction] = relationship(back_populates="reward_calc")
    reward_currency: Mapped[RewardCurrency] = relationship()
    rule_references: Mapped[list[CalcRuleReference]] = relationship(
        back_populates="calc", cascade="all, delete-orphan"
    )


class CalcRuleReference(Base):
    """Relational link from a calculation snapshot to each EarningRule version it used."""

    __tablename__ = "calc_rule_references"

    calc_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_reward_calcs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("earning_rules.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )

    calc: Mapped[TransactionRewardCalc] = relationship(back_populates="rule_references")
    rule: Mapped[EarningRule] = relationship()


class BenefitDefinition(Base):
    """Catalog definition of a card product benefit (credit, allowance, or perk)."""

    __tablename__ = "benefit_definitions"
    __table_args__ = (
        CheckConstraint(
            "benefit_type IN ('credit', 'allowance', 'perk')",
            name="ck_benefit_definitions_type",
        ),
        CheckConstraint(
            "value_cents IS NULL OR value_cents > 0",
            name="ck_benefit_definitions_value_pos",
        ),
        CheckConstraint(
            "reset_period IN ('monthly', 'quarterly', 'semiannual', 'calendar_year', 'card_year')",
            name="ck_benefit_definitions_reset_period",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_benefit_definitions_effective_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_product_id: Mapped[int] = mapped_column(
        ForeignKey("card_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    benefit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reset_period: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    source_id: Mapped[int] = mapped_column(
        ForeignKey("rule_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    card_product: Mapped[CardProduct] = relationship()
    source: Mapped[RuleSource] = relationship()
    usages: Mapped[list[BenefitUsage]] = relationship(back_populates="benefit_definition")


class BenefitUsage(Base):
    """User-logged usage entry against a benefit definition for a profile card."""

    __tablename__ = "benefit_usages"
    __table_args__ = (
        CheckConstraint(
            "amount_cents IS NULL OR amount_cents > 0",
            name="ck_benefit_usages_amount_pos",
        ),
        Index(
            "ix_benefit_usages_card_benefit_used_on",
            "profile_card_id",
            "benefit_definition_id",
            "used_on",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_card_id: Mapped[int] = mapped_column(
        ForeignKey("profile_cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    benefit_definition_id: Mapped[int] = mapped_column(
        ForeignKey("benefit_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))

    profile_card: Mapped[ProfileCard] = relationship(back_populates="benefit_usages")
    benefit_definition: Mapped[BenefitDefinition] = relationship(back_populates="usages")


async def is_rule_referenced(session: AsyncSession, rule_id: int) -> bool:
    """Return True if any persisted calculation snapshot references `rule_id`."""
    stmt = select(exists().where(CalcRuleReference.rule_id == rule_id))
    with session.no_autoflush:
        result = await session.scalar(stmt)
    return bool(result)


async def check_rule_mutable(session: AsyncSession, rule: EarningRule) -> None:
    """Enforce FR-6 / AC-8 immutability by checking CalcRuleReference before update."""
    referenced = await is_rule_referenced(session, rule.id)
    ensure_rule_mutable(rule, is_referenced_by_calc=referenced)
