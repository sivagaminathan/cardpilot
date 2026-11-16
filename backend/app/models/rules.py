"""SQLAlchemy 2.0 ORM models for earning rules, exclusions, and spend caps (T22).

Defines SpendCap, EarningRule, and RuleExclusion matching ARCHITECTURE.md §2.1-2.3.
Includes PostgreSQL btree_gist daterange non-overlap exclusion constraint on
earning_rules(rule_key, effective_from..effective_to) and the semantic-column
immutability guard boundary (wired to calculation references once
transaction_reward_calcs is added in T23).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    column,
    func,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.reference import CardProduct, Category, Merchant, RewardCurrency, RuleSource

SEMANTIC_RULE_COLUMNS: frozenset[str] = frozenset(
    {
        "rule_key",
        "version",
        "card_product_id",
        "reward_currency_id",
        "scope_type",
        "category_id",
        "merchant_id",
        "multiplier",
        "priority",
        "cap_id",
        "post_cap_behavior",
        "min_transaction_cents",
        "min_period_spend_cents",
        "threshold_period",
        "rounding",
        "effective_from",
        "effective_to",
        "source_id",
        "last_reviewed_on",
        "supersedes_id",
    }
)


class RuleImmutableError(ValueError):
    """Raised when attempting to mutate semantic columns on a referenced rule."""


def ensure_rule_mutable(rule: EarningRule, *, is_referenced_by_calc: bool) -> None:
    """Enforce FR-6 / AC-8 immutability once a rule is referenced by a calculation.

    Unreferenced rules may still be updated. Once referenced by a calculation
    (via transaction_reward_calcs introduced in T23), any pending modification to
    semantic columns on `rule` is rejected with RuleImmutableError.
    """
    if not is_referenced_by_calc:
        return

    insp = inspect(rule)
    dirty_semantic = [
        attr.key
        for attr in insp.attrs
        if attr.key in SEMANTIC_RULE_COLUMNS and attr.history.has_changes()
    ]
    if dirty_semantic:
        cols = ", ".join(sorted(dirty_semantic))
        raise RuleImmutableError(
            f"Rule '{rule.rule_key}' (id={rule.id}, v{rule.version}) is referenced by a "
            f"calculation and cannot modify semantic column(s): {cols}."
        )


class SpendCap(Base):
    """Spend cap defining maximum eligible spend per tracking period."""

    __tablename__ = "spend_caps"
    __table_args__ = (
        UniqueConstraint(
            "card_product_id",
            "cap_group_key",
            name="uq_spend_caps_card_product_cap_group_key",
        ),
        CheckConstraint("cap_amount_cents > 0", name="ck_spend_caps_amount_pos"),
        CheckConstraint(
            "period IN ('monthly', 'quarterly', 'calendar_year', 'card_year')",
            name="ck_spend_caps_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cap_group_key: Mapped[str] = mapped_column(String(128), nullable=False)
    card_product_id: Mapped[int] = mapped_column(
        ForeignKey("card_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cap_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False)

    card_product: Mapped[CardProduct] = relationship()
    rules: Mapped[list[EarningRule]] = relationship(back_populates="cap")


class EarningRule(Base):
    """Versioned earning rule for a card product, immutable once referenced."""

    __tablename__ = "earning_rules"
    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_earning_rules_rule_key_version"),
        CheckConstraint("version >= 1", name="ck_earning_rules_version_pos"),
        CheckConstraint(
            "scope_type IN ('base', 'category', 'merchant')",
            name="ck_earning_rules_scope_type",
        ),
        CheckConstraint(
            "(scope_type = 'base' AND category_id IS NULL AND merchant_id IS NULL) OR "
            "(scope_type = 'category' AND category_id IS NOT NULL AND merchant_id IS NULL) OR "
            "(scope_type = 'merchant' AND merchant_id IS NOT NULL AND category_id IS NULL)",
            name="ck_earning_rules_scope_target",
        ),
        CheckConstraint("multiplier >= 0", name="ck_earning_rules_multiplier_non_neg"),
        CheckConstraint(
            "post_cap_behavior IN ('fallback_to_base')",
            name="ck_earning_rules_post_cap_behavior",
        ),
        CheckConstraint(
            "min_transaction_cents IS NULL OR min_transaction_cents > 0",
            name="ck_earning_rules_min_tx_pos",
        ),
        CheckConstraint(
            "min_period_spend_cents IS NULL OR min_period_spend_cents > 0",
            name="ck_earning_rules_min_period_spend_pos",
        ),
        CheckConstraint(
            "threshold_period IS NULL OR "
            "threshold_period IN ('monthly', 'quarterly', 'calendar_year', 'card_year')",
            name="ck_earning_rules_threshold_period",
        ),
        CheckConstraint(
            "(min_period_spend_cents IS NULL) = (threshold_period IS NULL)",
            name="ck_earning_rules_threshold_pair",
        ),
        CheckConstraint(
            "rounding IN ('floor_units', 'nearest_unit', 'none_4dp')",
            name="ck_earning_rules_rounding",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_earning_rules_effective_range",
        ),
        ExcludeConstraint(
            (column("rule_key"), "="),
            (func.daterange(column("effective_from"), column("effective_to"), "[]"), "&&"),
            name="excl_earning_rules_rule_key_effective_range",
        ),
        Index(
            "ix_earning_rules_card_product_effective_from",
            "card_product_id",
            "effective_from",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    card_product_id: Mapped[int] = mapped_column(
        ForeignKey("card_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reward_currency_id: Mapped[int] = mapped_column(
        ForeignKey("reward_currencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    cap_id: Mapped[int | None] = mapped_column(
        ForeignKey("spend_caps.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    post_cap_behavior: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="fallback_to_base",
        server_default=text("'fallback_to_base'"),
    )
    min_transaction_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_period_spend_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threshold_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rounding: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="floor_units",
        server_default=text("'floor_units'"),
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("rule_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    last_reviewed_on: Mapped[date] = mapped_column(Date, nullable=False)
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("earning_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    card_product: Mapped[CardProduct] = relationship()
    reward_currency: Mapped[RewardCurrency] = relationship()
    category: Mapped[Category | None] = relationship()
    merchant: Mapped[Merchant | None] = relationship()
    cap: Mapped[SpendCap | None] = relationship(back_populates="rules")
    source: Mapped[RuleSource] = relationship()
    supersedes: Mapped[EarningRule | None] = relationship(remote_side="EarningRule.id")
    exclusions: Mapped[list[RuleExclusion]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class RuleExclusion(Base):
    """Typed exclusion attached to an earning rule."""

    __tablename__ = "rule_exclusions"
    __table_args__ = (
        CheckConstraint(
            "exclusion_type IN ('category', 'merchant', 'merchant_tag')",
            name="ck_rule_exclusions_type",
        ),
        CheckConstraint(
            "(exclusion_type = 'category' AND target_category_id IS NOT NULL "
            "AND target_merchant_id IS NULL AND target_tag IS NULL) OR "
            "(exclusion_type = 'merchant' AND target_merchant_id IS NOT NULL "
            "AND target_category_id IS NULL AND target_tag IS NULL) OR "
            "(exclusion_type = 'merchant_tag' AND target_tag IS NOT NULL "
            "AND length(btrim(target_tag)) > 0 "
            "AND target_category_id IS NULL AND target_merchant_id IS NULL)",
            name="ck_rule_exclusions_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("earning_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exclusion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    target_merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    target_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    rule: Mapped[EarningRule] = relationship(back_populates="exclusions")
    target_category: Mapped[Category | None] = relationship()
    target_merchant: Mapped[Merchant | None] = relationship()
