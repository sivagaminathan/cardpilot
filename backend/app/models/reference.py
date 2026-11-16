"""SQLAlchemy 2.0 ORM models for reference/catalog tables (T21).

Defines RewardCurrency, Category, Merchant, CardProduct, and RuleSource
matching ARCHITECTURE.md §2.1.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RewardCurrency(Base):
    """Reward currency earned by a card product (e.g., cash back, points, miles)."""

    __tablename__ = "reward_currencies"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('cash_back', 'points', 'miles')",
            name="ck_reward_currencies_kind",
        ),
        CheckConstraint(
            "default_cents_per_unit > 0",
            name="ck_reward_currencies_default_cents_per_unit_pos",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    is_cash_equivalent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    default_cents_per_unit: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)

    card_products: Mapped[list[CardProduct]] = relationship(back_populates="reward_currency")


class Category(Base):
    """Purchase spend category (e.g., dining, groceries, travel)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    merchants: Mapped[list[Merchant]] = relationship(back_populates="default_category")


class Merchant(Base):
    """Merchant reference entity with optional default category and tags."""

    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    default_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )

    default_category: Mapped[Category | None] = relationship(back_populates="merchants")


class CardProduct(Base):
    """Fictional credit card product linked to a reward currency."""

    __tablename__ = "card_products"
    __table_args__ = (
        UniqueConstraint("issuer_name", "name", name="uq_card_products_issuer_name"),
        CheckConstraint(
            "annual_fee_cents >= 0",
            name="ck_card_products_annual_fee_non_neg",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    reward_currency_id: Mapped[int] = mapped_column(
        ForeignKey("reward_currencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    annual_fee_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    network_label: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=text("''")
    )

    reward_currency: Mapped[RewardCurrency] = relationship(back_populates="card_products")


class RuleSource(Base):
    """Source metadata and last-reviewed date for earning rules and benefits."""

    __tablename__ = "rule_sources"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('fictional_sample', 'public_doc_example')",
            name="ck_rule_sources_kind",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    last_reviewed_on: Mapped[date] = mapped_column(Date, nullable=False)
