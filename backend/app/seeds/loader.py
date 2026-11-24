"""Idempotent YAML seed loader for CardPilot reference, rules, benefits, and demo profiles."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import close_engine, get_session_maker
from app.models import (
    BenefitDefinition,
    CardProduct,
    Category,
    CurrencyValuation,
    EarningRule,
    Merchant,
    Profile,
    ProfileCard,
    RewardCurrency,
    RuleExclusion,
    RuleSource,
    SpendCap,
    Transaction,
    check_rule_mutable,
    is_rule_referenced,
)

SEED_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_yaml(filename: str) -> dict[str, Any]:
    path = SEED_DATA_DIR / filename
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Seed file {filename} must contain a top-level mapping.")
    return loaded


def _opt_date(val: str | None) -> date | None:
    return date.fromisoformat(val) if val is not None else None


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Idempotently load all catalog data and demo profiles into the database."""
    counts: dict[str, int] = {}

    # 1. Currencies
    currencies_by_code: dict[str, RewardCurrency] = {}
    for item in _load_yaml("currencies.yaml")["currencies"]:
        cur = await session.scalar(
            select(RewardCurrency).where(RewardCurrency.code == item["code"])
        )
        if cur is None:
            cur = RewardCurrency(
                code=item["code"],
                name=item["name"],
                kind=item["kind"],
                is_cash_equivalent=bool(item["is_cash_equivalent"]),
                default_cents_per_unit=Decimal(str(item["default_cents_per_unit"])),
            )
            session.add(cur)
        else:
            cur.name = item["name"]
            cur.kind = item["kind"]
            cur.is_cash_equivalent = bool(item["is_cash_equivalent"])
            cur.default_cents_per_unit = Decimal(str(item["default_cents_per_unit"]))
        currencies_by_code[item["code"]] = cur
    await session.flush()
    counts["currencies"] = len(currencies_by_code)

    # 2. Categories
    categories_by_code: dict[str, Category] = {}
    for item in _load_yaml("categories.yaml")["categories"]:
        cat = await session.scalar(select(Category).where(Category.code == item["code"]))
        if cat is None:
            cat = Category(code=item["code"], name=item["name"])
            session.add(cat)
        else:
            cat.name = item["name"]
        categories_by_code[item["code"]] = cat
    await session.flush()
    counts["categories"] = len(categories_by_code)

    # 3. Merchants
    merchants_by_name: dict[str, Merchant] = {}
    for item in _load_yaml("merchants.yaml")["merchants"]:
        cat_code = item.get("default_category_code")
        default_cat_id = categories_by_code[cat_code].id if cat_code else None
        merch = await session.scalar(select(Merchant).where(Merchant.name == item["name"]))
        if merch is None:
            merch = Merchant(
                name=item["name"],
                default_category_id=default_cat_id,
                tags=list(item.get("tags", [])),
            )
            session.add(merch)
        else:
            merch.default_category_id = default_cat_id
            merch.tags = list(item.get("tags", []))
        merchants_by_name[item["name"]] = merch
    await session.flush()
    counts["merchants"] = len(merchants_by_name)

    # 4. Sources
    sources_by_title: dict[str, RuleSource] = {}
    for item in _load_yaml("sources.yaml")["sources"]:
        src = await session.scalar(select(RuleSource).where(RuleSource.title == item["title"]))
        if src is None:
            src = RuleSource(
                title=item["title"],
                kind=item["kind"],
                url=item.get("url"),
                notes=item.get("notes", ""),
                last_reviewed_on=date.fromisoformat(item["last_reviewed_on"]),
            )
            session.add(src)
        else:
            src.kind = item["kind"]
            src.url = item.get("url")
            src.notes = item.get("notes", "")
            src.last_reviewed_on = date.fromisoformat(item["last_reviewed_on"])
        sources_by_title[item["title"]] = src
    await session.flush()
    counts["sources"] = len(sources_by_title)

    # 5. Card Products
    products_by_key: dict[tuple[str, str], CardProduct] = {}
    for item in _load_yaml("card_products.yaml")["card_products"]:
        pkey = (item["issuer_name"], item["name"])
        currency_id = currencies_by_code[item["reward_currency_code"]].id
        prod = await session.scalar(
            select(CardProduct).where(
                CardProduct.issuer_name == item["issuer_name"],
                CardProduct.name == item["name"],
            )
        )
        if prod is None:
            prod = CardProduct(
                issuer_name=item["issuer_name"],
                name=item["name"],
                reward_currency_id=currency_id,
                annual_fee_cents=int(item.get("annual_fee_cents", 0)),
                network_label=item["network_label"],
                description=item.get("description", ""),
            )
            session.add(prod)
        else:
            prod.reward_currency_id = currency_id
            prod.annual_fee_cents = int(item.get("annual_fee_cents", 0))
            prod.network_label = item["network_label"]
            prod.description = item.get("description", "")
        products_by_key[pkey] = prod
    await session.flush()
    counts["card_products"] = len(products_by_key)

    # 6. Spend Caps, Earning Rules, and Exclusions
    rules_doc = _load_yaml("rules.yaml")
    caps_by_key: dict[str, SpendCap] = {}
    for item in rules_doc["spend_caps"]:
        pkey = (item["card_product"]["issuer_name"], item["card_product"]["name"])
        card_prod = products_by_key[pkey]
        cap = await session.scalar(
            select(SpendCap).where(
                SpendCap.card_product_id == card_prod.id,
                SpendCap.cap_group_key == item["cap_group_key"],
            )
        )
        if cap is None:
            cap = SpendCap(
                cap_group_key=item["cap_group_key"],
                card_product_id=card_prod.id,
                cap_amount_cents=int(item["cap_amount_cents"]),
                period=item["period"],
            )
            session.add(cap)
        else:
            cap.cap_amount_cents = int(item["cap_amount_cents"])
            cap.period = item["period"]
        caps_by_key[item["cap_group_key"]] = cap
    await session.flush()

    rules_by_key: dict[tuple[str, int], EarningRule] = {}
    sorted_rules = sorted(rules_doc["earning_rules"], key=lambda r: (r["rule_key"], r["version"]))
    for item in sorted_rules:
        pkey = (item["card_product"]["issuer_name"], item["card_product"]["name"])
        card_prod = products_by_key[pkey]
        currency_id = currencies_by_code[item["reward_currency_code"]].id
        cat_code = item.get("category_code")
        merch_name = item.get("merchant_name")
        cap_key = item.get("cap_group_key")
        sup = item.get("supersedes")
        supersedes_id = rules_by_key[(sup["rule_key"], int(sup["version"]))].id if sup else None

        rule = await session.scalar(
            select(EarningRule).where(
                EarningRule.rule_key == item["rule_key"],
                EarningRule.version == int(item["version"]),
            )
        )
        if rule is None:
            rule = EarningRule(
                rule_key=item["rule_key"],
                version=int(item["version"]),
                card_product_id=card_prod.id,
                reward_currency_id=currency_id,
                scope_type=item["scope_type"],
                category_id=categories_by_code[cat_code].id if cat_code else None,
                merchant_id=merchants_by_name[merch_name].id if merch_name else None,
                multiplier=Decimal(str(item["multiplier"])),
                priority=int(item.get("priority", 0)),
                cap_id=caps_by_key[cap_key].id if cap_key else None,
                post_cap_behavior=item.get("post_cap_behavior", "fallback_to_base"),
                min_transaction_cents=item.get("min_transaction_cents"),
                min_period_spend_cents=item.get("min_period_spend_cents"),
                threshold_period=item.get("threshold_period"),
                rounding=item.get("rounding", "floor_units"),
                effective_from=date.fromisoformat(item["effective_from"]),
                effective_to=_opt_date(item.get("effective_to")),
                source_id=sources_by_title[item["source_title"]].id,
                last_reviewed_on=date.fromisoformat(item["last_reviewed_on"]),
                supersedes_id=supersedes_id,
            )
            session.add(rule)
        elif not await is_rule_referenced(session, rule.id):
            rule.card_product_id = card_prod.id
            rule.reward_currency_id = currency_id
            rule.scope_type = item["scope_type"]
            rule.category_id = categories_by_code[cat_code].id if cat_code else None
            rule.merchant_id = merchants_by_name[merch_name].id if merch_name else None
            rule.multiplier = Decimal(str(item["multiplier"]))
            rule.priority = int(item.get("priority", 0))
            rule.cap_id = caps_by_key[cap_key].id if cap_key else None
            rule.post_cap_behavior = item.get("post_cap_behavior", "fallback_to_base")
            rule.min_transaction_cents = item.get("min_transaction_cents")
            rule.min_period_spend_cents = item.get("min_period_spend_cents")
            rule.threshold_period = item.get("threshold_period")
            rule.rounding = item.get("rounding", "floor_units")
            rule.effective_from = date.fromisoformat(item["effective_from"])
            rule.effective_to = _opt_date(item.get("effective_to"))
            rule.source_id = sources_by_title[item["source_title"]].id
            rule.last_reviewed_on = date.fromisoformat(item["last_reviewed_on"])
            rule.supersedes_id = supersedes_id
            await check_rule_mutable(session, rule)

        await session.flush()
        rules_by_key[(item["rule_key"], int(item["version"]))] = rule
    counts["earning_rules"] = len(rules_by_key)

    for item in rules_doc["rule_exclusions"]:
        rule = rules_by_key[(item["rule_key"], int(item["rule_version"]))]
        ex_type = item["exclusion_type"]
        target_cat_id = (
            categories_by_code[item["target_category_code"]].id if ex_type == "category" else None
        )
        target_merch_id = (
            merchants_by_name[item["target_merchant_name"]].id if ex_type == "merchant" else None
        )
        target_tag = item.get("target_tag") if ex_type == "merchant_tag" else None

        existing_ex = await session.scalar(
            select(RuleExclusion).where(
                RuleExclusion.rule_id == rule.id,
                RuleExclusion.exclusion_type == ex_type,
                RuleExclusion.target_category_id == target_cat_id,
                RuleExclusion.target_merchant_id == target_merch_id,
                RuleExclusion.target_tag == target_tag,
            )
        )
        if existing_ex is None:
            session.add(
                RuleExclusion(
                    rule_id=rule.id,
                    exclusion_type=ex_type,
                    target_category_id=target_cat_id,
                    target_merchant_id=target_merch_id,
                    target_tag=target_tag,
                    reason=item["reason"],
                )
            )
    await session.flush()

    # 7. Benefit Definitions
    benefit_count = 0
    for item in _load_yaml("benefits.yaml")["benefits"]:
        pkey = (item["card_product"]["issuer_name"], item["card_product"]["name"])
        card_prod = products_by_key[pkey]
        eff_from = date.fromisoformat(item["effective_from"])
        benefit = await session.scalar(
            select(BenefitDefinition).where(
                BenefitDefinition.card_product_id == card_prod.id,
                BenefitDefinition.name == item["name"],
                BenefitDefinition.effective_from == eff_from,
            )
        )
        if benefit is None:
            session.add(
                BenefitDefinition(
                    card_product_id=card_prod.id,
                    name=item["name"],
                    benefit_type=item["benefit_type"],
                    value_cents=item.get("value_cents"),
                    reset_period=item["reset_period"],
                    notes=item.get("notes", ""),
                    source_id=sources_by_title[item["source_title"]].id,
                    effective_from=eff_from,
                    effective_to=_opt_date(item.get("effective_to")),
                )
            )
        benefit_count += 1
    await session.flush()
    counts["benefits"] = benefit_count

    # 8. Demo Profiles
    profile_count = 0
    for item in _load_yaml("profiles.yaml")["profiles"]:
        profile = await session.scalar(select(Profile).where(Profile.seed_key == item["seed_key"]))
        if profile is None:
            profile = Profile(
                slug=item["slug"],
                display_name=item["display_name"],
                is_demo=bool(item.get("is_demo", True)),
                seed_key=item["seed_key"],
            )
            session.add(profile)
            await session.flush()
        else:
            profile.slug = item["slug"]
            profile.display_name = item["display_name"]

        for card_cfg in item.get("cards", []):
            pkey = (
                card_cfg["card_product"]["issuer_name"],
                card_cfg["card_product"]["name"],
            )
            card_prod = products_by_key[pkey]
            existing_pc = await session.scalar(
                select(ProfileCard).where(
                    ProfileCard.profile_id == profile.id,
                    ProfileCard.card_product_id == card_prod.id,
                    ProfileCard.nickname == card_cfg["nickname"],
                )
            )
            if existing_pc is None:
                session.add(
                    ProfileCard(
                        profile_id=profile.id,
                        card_product_id=card_prod.id,
                        nickname=card_cfg["nickname"],
                        opened_on=_opt_date(card_cfg.get("opened_on")),
                        is_active=True,
                    )
                )

        for val_cfg in item.get("valuations", []):
            curr = currencies_by_code[val_cfg["reward_currency_code"]]
            existing_val = await session.scalar(
                select(CurrencyValuation).where(
                    CurrencyValuation.profile_id == profile.id,
                    CurrencyValuation.reward_currency_id == curr.id,
                )
            )
            if existing_val is None:
                session.add(
                    CurrencyValuation(
                        profile_id=profile.id,
                        reward_currency_id=curr.id,
                        cents_per_unit=Decimal(str(val_cfg["cents_per_unit"])),
                        is_user_set=bool(val_cfg.get("is_user_set", False)),
                    )
                )
        profile_count += 1
    await session.flush()
    counts["profiles"] = profile_count
    return counts


async def ensure_seeded(session: AsyncSession) -> None:
    """Seed the database if no profiles exist yet."""
    has_profiles = await session.scalar(select(exists().select_from(Profile)))
    if not has_profiles:
        await seed_all(session)


async def reset_profile_to_seed(session: AsyncSession, profile: Profile) -> tuple[int, int]:
    """Reset a single demo profile's cards, valuations, transactions, and usages to seed state."""
    if not profile.is_demo or not profile.seed_key:
        raise ValueError(f"Profile '{profile.slug}' is not a resettable demo profile.")

    profiles_doc = _load_yaml("profiles.yaml")["profiles"]
    seed_cfg = next((p for p in profiles_doc if p.get("seed_key") == profile.seed_key), None)
    if seed_cfg is None:
        raise ValueError(f"No seed definition found for profile '{profile.slug}'.")

    await session.execute(delete(Transaction).where(Transaction.profile_id == profile.id))
    await session.execute(
        delete(CurrencyValuation).where(CurrencyValuation.profile_id == profile.id)
    )
    await session.execute(delete(ProfileCard).where(ProfileCard.profile_id == profile.id))
    await session.flush()

    profile.slug = seed_cfg["slug"]
    profile.display_name = seed_cfg["display_name"]
    profile.is_demo = bool(seed_cfg.get("is_demo", True))

    all_products = (await session.scalars(select(CardProduct))).all()
    products_by_key = {(p.issuer_name, p.name): p for p in all_products}
    all_currencies = (await session.scalars(select(RewardCurrency))).all()
    currencies_by_code = {c.code: c for c in all_currencies}

    cards_restored = 0
    for card_cfg in seed_cfg.get("cards", []):
        pkey = (
            card_cfg["card_product"]["issuer_name"],
            card_cfg["card_product"]["name"],
        )
        card_prod = products_by_key[pkey]
        session.add(
            ProfileCard(
                profile_id=profile.id,
                card_product_id=card_prod.id,
                nickname=card_cfg["nickname"],
                opened_on=_opt_date(card_cfg.get("opened_on")),
                is_active=True,
            )
        )
        cards_restored += 1

    valuations_restored = 0
    for val_cfg in seed_cfg.get("valuations", []):
        curr = currencies_by_code[val_cfg["reward_currency_code"]]
        session.add(
            CurrencyValuation(
                profile_id=profile.id,
                reward_currency_id=curr.id,
                cents_per_unit=Decimal(str(val_cfg["cents_per_unit"])),
                is_user_set=bool(val_cfg.get("is_user_set", False)),
            )
        )
        valuations_restored += 1

    await session.flush()
    return cards_restored, valuations_restored


async def _main(*, if_empty: bool = False) -> None:
    session_factory = get_session_maker()
    try:
        async with session_factory() as session, session.begin():
            if if_empty:
                await ensure_seeded(session)
                print("Checked seed state (seed-on-first-deploy complete).")
            else:
                counts = await seed_all(session)
                print(f"Seeded CardPilot catalog and demo profiles: {counts}")
    finally:
        await close_engine()


if __name__ == "__main__":
    import sys

    asyncio.run(_main(if_empty="--if-empty" in sys.argv[1:]))
