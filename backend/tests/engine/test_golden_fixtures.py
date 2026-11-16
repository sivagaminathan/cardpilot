"""Golden fixture suite and orchestrator tests for the pure reward engine (T20).

Loads >= 15 JSON scenarios from tests/engine/fixtures/scenarios.json, executes
evaluate_purchase + rank_card_evaluations end-to-end, and asserts exact
expected outcomes across AC-2..AC-10 and AC-13 without mocking or generating
expected values from production code.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.engine import (
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    ExclusionType,
    IneligibleReason,
    Period,
    Purchase,
    RoundingMode,
    RuleExclusion,
    ScopeType,
    SpendCap,
    SpendHistory,
    Valuation,
    evaluate_purchase,
    rank_card_evaluations,
)

_FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "scenarios.json"


def _load_scenarios() -> list[dict[str, Any]]:
    data = json.loads(_FIXTURES_PATH.read_text(encoding="utf-8"))
    scenarios: list[dict[str, Any]] = data["scenarios"]
    return scenarios


def _parse_purchase(raw: dict[str, Any]) -> Purchase:
    return Purchase(
        amount_cents=raw["amount_cents"],
        category=raw["category"],
        purchase_date=date.fromisoformat(raw["purchase_date"]),
        merchant=raw.get("merchant"),
        merchant_tags=tuple(raw.get("merchant_tags", ())),
    )


def _parse_rule(raw: dict[str, Any]) -> EarningRule:
    exclusions = tuple(
        RuleExclusion(
            exclusion_type=ExclusionType(ex["exclusion_type"]),
            target=ex["target"],
            reason=ex["reason"],
        )
        for ex in raw.get("exclusions", ())
    )
    eff_to = date.fromisoformat(raw["effective_to"]) if raw.get("effective_to") else None
    thresh_period = Period(raw["threshold_period"]) if raw.get("threshold_period") else None
    return EarningRule(
        id=raw["id"],
        rule_key=raw["rule_key"],
        version=raw["version"],
        scope_type=ScopeType(raw["scope_type"]),
        multiplier=Decimal(raw["multiplier"]),
        effective_from=date.fromisoformat(raw["effective_from"]),
        effective_to=eff_to,
        category=raw.get("category"),
        merchant=raw.get("merchant"),
        priority=raw.get("priority", 0),
        cap_group_key=raw.get("cap_group_key"),
        min_transaction_cents=raw.get("min_transaction_cents"),
        min_period_spend_cents=raw.get("min_period_spend_cents"),
        threshold_period=thresh_period,
        rounding=RoundingMode(raw.get("rounding", "floor_units")),
        exclusions=exclusions,
        description=raw.get("description", ""),
    )


def _parse_card(
    raw: dict[str, Any],
) -> tuple[CardContext, SpendHistory, Valuation | None]:
    rules = tuple(_parse_rule(r) for r in raw["rules"])
    caps = tuple(
        SpendCap(
            cap_group_key=c["cap_group_key"],
            cap_amount_cents=c["cap_amount_cents"],
            period=Period(c["period"]),
        )
        for c in raw.get("caps", ())
    )
    card = CardContext(
        card_id=raw["card_id"],
        card_name=raw["card_name"],
        reward_currency=raw["reward_currency"],
        rules=rules,
        caps=caps,
    )
    raw_hist = raw.get("spend_history", {})
    history = SpendHistory(
        cap_spend_cents=raw_hist.get("cap_spend_cents", {}),
        threshold_spend_cents=raw_hist.get("threshold_spend_cents", {}),
    )
    raw_val = raw.get("valuation")
    valuation = (
        Valuation(
            reward_currency=raw_val["reward_currency"],
            cents_per_unit=Decimal(raw_val["cents_per_unit"]),
            is_user_set=raw_val["is_user_set"],
        )
        if raw_val is not None
        else None
    )
    return card, history, valuation


def _assert_card_matches(actual: CardEvaluation, expected: dict[str, Any]) -> None:
    assert actual.card_id == expected["card_id"]
    if "reward_currency" in expected:
        assert actual.reward_currency == expected["reward_currency"]
    if "reward_units" in expected:
        assert actual.reward_units == Decimal(expected["reward_units"])
        assert str(actual.reward_units) == expected["reward_units"]
    if "estimated_value_cents" in expected:
        assert actual.estimated_value_cents == expected["estimated_value_cents"]
    if "rejection_reason" in expected:
        assert actual.rejection_reason == expected["rejection_reason"]
    if "rejection_message" in expected:
        assert actual.rejection_message == expected["rejection_message"]
    if "warnings" in expected:
        assert actual.warnings == tuple(expected["warnings"])
    if "applied_portions" in expected:
        exp_portions = expected["applied_portions"]
        assert len(actual.applied_portions) == len(exp_portions)
        for act_p, exp_p in zip(actual.applied_portions, exp_portions, strict=True):
            assert act_p.portion_cents == exp_p["portion_cents"]
            assert act_p.rule_id == exp_p["rule_id"]
            assert act_p.rule_version == exp_p["rule_version"]
            assert act_p.multiplier == Decimal(exp_p["multiplier"])
    if "explanation_contains" in expected:
        joined = " ".join(actual.explanation)
        for snippet in expected["explanation_contains"]:
            assert snippet in joined


_SCENARIOS = _load_scenarios()


def test_at_least_15_golden_scenarios_exist() -> None:
    assert len(_SCENARIOS) >= 15
    ids = [s["id"] for s in _SCENARIOS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s["id"] for s in _SCENARIOS])
def test_golden_scenario(scenario: dict[str, Any]) -> None:
    purchase = _parse_purchase(scenario["purchase"])

    evaluations: list[CardEvaluation] = []
    for raw_card in scenario["cards"]:
        card, history, valuation = _parse_card(raw_card)
        ev = evaluate_purchase(purchase, card, history, valuation)
        # Trace step numbers must be contiguous 1..N
        assert [t.step_number for t in ev.trace] == list(range(1, len(ev.trace) + 1))
        assert len(ev.explanation) == len(ev.trace)
        evaluations.append(ev)

    result_1 = rank_card_evaluations(evaluations)
    result_2 = rank_card_evaluations(evaluations)
    assert result_1 == result_2  # AC-13 determinism

    expected = scenario["expected"]
    assert len(result_1.ranked) == len(expected["ranked"])
    for act, exp in zip(result_1.ranked, expected["ranked"], strict=True):
        _assert_card_matches(act, exp)

    assert len(result_1.unranked) == len(expected["unranked"])
    for act, exp in zip(result_1.unranked, expected["unranked"], strict=True):
        _assert_card_matches(act, exp)

    assert len(result_1.ineligible) == len(expected["ineligible"])
    for act, exp in zip(result_1.ineligible, expected["ineligible"], strict=True):
        _assert_card_matches(act, exp)

    if "global_notes" in expected:
        assert result_1.global_notes == tuple(expected["global_notes"])


class TestEvaluatePurchaseEdgeCases:
    """Direct tests for evaluate_purchase edge paths."""

    def test_all_applicable_caps_exhausted_returns_ineligible(self) -> None:
        capped_rule = EarningRule(
            id=1,
            rule_key="dining.5x_q",
            version=1,
            scope_type=ScopeType.CATEGORY,
            category="dining",
            multiplier=Decimal("5.0"),
            cap_group_key="dining_q",
            effective_from=date(2026, 1, 1),
        )
        cap = SpendCap(
            cap_group_key="dining_q",
            cap_amount_cents=50000,
            period=Period.QUARTERLY,
        )
        card = CardContext(
            card_id=99,
            card_name="Capped Only",
            reward_currency="POINTS",
            rules=(capped_rule,),
            caps=(cap,),
        )
        purchase = Purchase(amount_cents=5000, category="dining", purchase_date=date(2026, 11, 15))
        history = SpendHistory(cap_spend_cents={"dining_q": 50000})

        ev = evaluate_purchase(
            purchase,
            card,
            history,
            Valuation("POINTS", Decimal("1.0"), is_user_set=True),
        )

        assert ev.status == CardStatus.INELIGIBLE
        assert ev.reward_units == Decimal("0")
        assert ev.estimated_value_cents is None
        assert ev.rejection_reason == IneligibleReason.NO_APPLICABLE_RULE.value
        assert [t.step_number for t in ev.trace] == list(range(1, len(ev.trace) + 1))
        assert len(ev.explanation) == len(ev.trace)
