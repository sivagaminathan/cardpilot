"""Validation tests for T24 fictional YAML seed data files."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

SEED_DIR = Path(__file__).resolve().parents[2] / "app" / "seeds" / "data"

FORBIDDEN_REAL_NAMES = (
    "chase",
    "amex",
    "american express",
    "citibank",
    "citi",
    "capital one",
    "discover",
    "wells fargo",
    "bank of america",
    "visa",
    "mastercard",
    "costco",
    "walmart",
    "target",
    "starbucks",
    "delta",
    "united",
)

PAN_DIGITS_RE = re.compile(r"\b\d{13,19}\b")


def _load_yaml(filename: str) -> dict[str, Any]:
    path = SEED_DIR / filename
    assert path.exists(), f"Missing seed file: {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{filename} must have a top-level mapping"
    return data


def _parse_iso_date(value: Any, field: str) -> date:
    assert isinstance(value, str), f"{field} must be an ISO-8601 string, got {type(value).__name__}"
    return date.fromisoformat(value)


def _ranges_overlap(
    start_a: date,
    end_a: date | None,
    start_b: date,
    end_b: date | None,
) -> bool:
    eff_end_a = end_a or date.max
    eff_end_b = end_b or date.max
    return start_a <= eff_end_b and start_b <= eff_end_a


def test_currencies_seed_data() -> None:
    items = _load_yaml("currencies.yaml")["currencies"]
    assert len(items) >= 3
    codes = {c["code"] for c in items}
    assert len(codes) == len(items)
    kinds = {c["kind"] for c in items}
    assert {"cash_back", "points", "miles"}.issubset(kinds)

    for c in items:
        assert c["is_fictional"] is True
        val = c["default_cents_per_unit"]
        assert isinstance(val, str), "default_cents_per_unit must be a YAML string"
        assert Decimal(val) > Decimal("0")


def test_categories_and_merchants_seed_data() -> None:
    cats = _load_yaml("categories.yaml")["categories"]
    cat_codes = {c["code"] for c in cats}
    assert len(cat_codes) == len(cats)
    assert {
        "dining",
        "groceries",
        "gas",
        "travel",
        "streaming",
        "online_retail",
        "utilities",
        "other",
    }.issubset(cat_codes)

    merchants = _load_yaml("merchants.yaml")["merchants"]
    names = {m["name"] for m in merchants}
    assert len(names) == len(merchants)
    all_tags: set[str] = set()
    for m in merchants:
        assert m["default_category_code"] in cat_codes
        assert isinstance(m["tags"], list)
        all_tags.update(m["tags"])
    assert {"warehouse_club", "big_box"}.issubset(all_tags)


def test_sources_and_card_products_seed_data() -> None:
    sources = _load_yaml("sources.yaml")["sources"]
    source_titles = {s["title"] for s in sources}
    assert len(source_titles) == len(sources)
    for s in sources:
        assert s["kind"] == "fictional_sample"
        _parse_iso_date(s["last_reviewed_on"], "last_reviewed_on")
        assert "fictional" in s["notes"].lower()

    currency_codes = {c["code"] for c in _load_yaml("currencies.yaml")["currencies"]}
    products = _load_yaml("card_products.yaml")["card_products"]
    assert len(products) >= 6

    product_keys = {(p["issuer_name"], p["name"]) for p in products}
    assert len(product_keys) == len(products)
    styles = {p["style"] for p in products}
    assert {
        "cash_back",
        "flexible_points",
        "airline_miles",
        "flat_rate",
        "category_specialist",
    }.issubset(styles)

    for p in products:
        assert p["is_fictional"] is True
        assert p["reward_currency_code"] in currency_codes
        assert isinstance(p["annual_fee_cents"], int) and not isinstance(
            p["annual_fee_cents"], bool
        )
        assert p["annual_fee_cents"] >= 0


def test_rules_caps_and_exclusions_seed_data() -> None:
    currency_codes = {c["code"] for c in _load_yaml("currencies.yaml")["currencies"]}
    cat_codes = {c["code"] for c in _load_yaml("categories.yaml")["categories"]}
    merchant_names = {m["name"] for m in _load_yaml("merchants.yaml")["merchants"]}
    source_titles = {s["title"] for s in _load_yaml("sources.yaml")["sources"]}
    product_keys = {
        (p["issuer_name"], p["name"]) for p in _load_yaml("card_products.yaml")["card_products"]
    }

    rules_doc = _load_yaml("rules.yaml")
    caps = rules_doc["spend_caps"]
    rules = rules_doc["earning_rules"]
    exclusions = rules_doc["rule_exclusions"]

    cap_keys: set[str] = set()
    for cap in caps:
        pkey = (cap["card_product"]["issuer_name"], cap["card_product"]["name"])
        assert pkey in product_keys
        assert cap["cap_group_key"] not in cap_keys
        cap_keys.add(cap["cap_group_key"])
        assert isinstance(cap["cap_amount_cents"], int) and cap["cap_amount_cents"] > 0
        assert cap["period"] in {"monthly", "quarterly", "calendar_year", "card_year"}

    rule_versions: dict[tuple[str, int], dict[str, Any]] = {}
    ranges_by_key: dict[str, list[tuple[date, date | None]]] = {}
    base_products: set[tuple[str, str]] = set()

    for r in rules:
        assert r["is_fictional"] is True
        assert r["source_title"] in source_titles
        _parse_iso_date(r["last_reviewed_on"], "last_reviewed_on")
        eff_from = _parse_iso_date(r["effective_from"], "effective_from")
        eff_to = (
            _parse_iso_date(r["effective_to"], "effective_to")
            if r["effective_to"] is not None
            else None
        )
        if eff_to is not None:
            assert eff_to >= eff_from

        pkey = (r["card_product"]["issuer_name"], r["card_product"]["name"])
        assert pkey in product_keys
        assert r["reward_currency_code"] in currency_codes

        assert isinstance(r["multiplier"], str)
        assert Decimal(r["multiplier"]) >= Decimal("0")

        rv_key = (r["rule_key"], r["version"])
        assert rv_key not in rule_versions
        rule_versions[rv_key] = r

        for prev_from, prev_to in ranges_by_key.setdefault(r["rule_key"], []):
            assert not _ranges_overlap(eff_from, eff_to, prev_from, prev_to), (
                f"Overlapping dates for {r['rule_key']}"
            )
        ranges_by_key[r["rule_key"]].append((eff_from, eff_to))

        if r["scope_type"] == "base":
            base_products.add(pkey)
        elif r["scope_type"] == "category":
            assert r["category_code"] in cat_codes
        elif r["scope_type"] == "merchant":
            assert r["merchant_name"] in merchant_names
        else:
            raise AssertionError(f"Unknown scope_type: {r['scope_type']}")

        if "cap_group_key" in r:
            assert r["cap_group_key"] in cap_keys

    # Every seeded product has a base fallback rule
    assert base_products == product_keys

    # Required examples: superseded version, capped rule, threshold rule, exclusion
    superseded = [r for r in rules if "supersedes" in r]
    assert len(superseded) >= 1
    for r in superseded:
        sup = r["supersedes"]
        assert (sup["rule_key"], sup["version"]) in rule_versions

    assert any("cap_group_key" in r for r in rules)
    assert any("min_transaction_cents" in r or "min_period_spend_cents" in r for r in rules)
    assert len(exclusions) >= 1
    for ex in exclusions:
        assert (ex["rule_key"], ex["rule_version"]) in rule_versions
        assert ex["exclusion_type"] in {"category", "merchant", "merchant_tag"}
    assert any(ex.get("target_tag") == "warehouse_club" for ex in exclusions)


def test_benefits_seed_data() -> None:
    source_titles = {s["title"] for s in _load_yaml("sources.yaml")["sources"]}
    product_keys = {
        (p["issuer_name"], p["name"]) for p in _load_yaml("card_products.yaml")["card_products"]
    }
    benefits = _load_yaml("benefits.yaml")["benefits"]
    assert len(benefits) >= 3
    types_seen: set[str] = set()

    for b in benefits:
        assert b["is_fictional"] is True
        pkey = (b["card_product"]["issuer_name"], b["card_product"]["name"])
        assert pkey in product_keys
        assert b["source_title"] in source_titles
        assert b["benefit_type"] in {"credit", "allowance", "perk"}
        types_seen.add(b["benefit_type"])
        assert b["reset_period"] in {
            "monthly",
            "quarterly",
            "semiannual",
            "calendar_year",
            "card_year",
        }
        val = b["value_cents"]
        assert val is None or (isinstance(val, int) and not isinstance(val, bool) and val > 0)
        eff_from = _parse_iso_date(b["effective_from"], "effective_from")
        if b["effective_to"] is not None:
            assert _parse_iso_date(b["effective_to"], "effective_to") >= eff_from

    assert {"credit", "allowance", "perk"}.issubset(types_seen)


def test_no_real_names_or_sensitive_digits_in_seed_files() -> None:
    for yaml_path in sorted(SEED_DIR.glob("*.yaml")):
        raw = yaml_path.read_text(encoding="utf-8")
        lowered = raw.lower()
        for forbidden in FORBIDDEN_REAL_NAMES:
            assert not re.search(rf"\b{re.escape(forbidden)}\b", lowered), (
                f"Forbidden real name '{forbidden}' in {yaml_path.name}"
            )
        assert not PAN_DIGITS_RE.search(raw), f"Sensitive digit sequence in {yaml_path.name}"
