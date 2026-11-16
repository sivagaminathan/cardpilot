"""Deterministic rule selection for the reward engine (T11, AC-3, AC-13).

Selects a single winning rule from applicable rules by sorting on:
1. Scope specificity descending (MERCHANT=3, CATEGORY=2, BASE=1)
2. Explicit priority descending
3. Stable rule ID ascending

Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.engine.types import (
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    IneligibleReason,
    Purchase,
    ScopeType,
    TraceStep,
    _normalize_sequence,
)

_SPECIFICITY_WEIGHT: dict[ScopeType, int] = {
    ScopeType.MERCHANT: 3,
    ScopeType.CATEGORY: 2,
    ScopeType.BASE: 1,
}


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Result of deterministic rule selection among applicable rules."""

    winning_rule: EarningRule
    alternative_rules: tuple[EarningRule, ...]
    trace_steps: tuple[TraceStep, ...]
    explanation: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "alternative_rules",
            _normalize_sequence(self.alternative_rules, "alternative_rules"),
        )
        object.__setattr__(
            self,
            "trace_steps",
            _normalize_sequence(self.trace_steps, "trace_steps"),
        )


def _rule_label(rule: EarningRule) -> str:
    """Return a concise, human-readable label identifying a rule."""
    desc_part = f" '{rule.description}'" if rule.description.strip() else ""
    return (
        f"rule '{rule.rule_key}'{desc_part} "
        f"(v{rule.version}, {rule.scope_type.value}, {rule.multiplier}x, id={rule.id})"
    )


def sort_rules_by_selection_priority(
    rules: Sequence[EarningRule],
) -> tuple[EarningRule, ...]:
    """Sort applicable rules in deterministic winner-first order.

    Order: specificity desc (MERCHANT > CATEGORY > BASE), priority desc, rule_id asc.
    Raises ValueError if duplicate rule IDs are present, as unique rule IDs are required
    for strict tie-break determinism.
    """
    seen_ids: set[int] = set()
    for rule in rules:
        if rule.id in seen_ids:
            raise ValueError(f"Duplicate rule id {rule.id} in selection input")
        seen_ids.add(rule.id)

    return tuple(
        sorted(
            rules,
            key=lambda r: (-_SPECIFICITY_WEIGHT[r.scope_type], -r.priority, r.id),
        )
    )


def _alternative_loss_reason(
    winner: EarningRule,
    alternative: EarningRule,
) -> tuple[str, str]:
    """Determine stable reason and detail explaining why an alternative rule was not selected."""
    winner_spec = _SPECIFICITY_WEIGHT[winner.scope_type]
    alt_spec = _SPECIFICITY_WEIGHT[alternative.scope_type]

    if winner_spec > alt_spec:
        return (
            "lower_specificity",
            f"Not selected: {_rule_label(alternative)} has lower scope specificity "
            f"({alternative.scope_type.value}) than winning {_rule_label(winner)}.",
        )

    if winner.priority > alternative.priority:
        return (
            "lower_priority",
            f"Not selected: {_rule_label(alternative)} has lower priority "
            f"({alternative.priority}) than winning {_rule_label(winner)} "
            f"(priority={winner.priority}).",
        )

    return (
        "rule_id_tie_break",
        f"Not selected: {_rule_label(alternative)} lost deterministic rule ID tie-break "
        f"({alternative.id} > {winner.id}) against winning {_rule_label(winner)}.",
    )


def select_best_rule(rules: Sequence[EarningRule]) -> SelectionResult | None:
    """Select the single winning rule from applicable rules and record alternatives.

    Returns None when no applicable rules are provided.
    """
    if not rules:
        return None

    ordered = sort_rules_by_selection_priority(rules)
    winner = ordered[0]
    alternatives = ordered[1:]

    winner_detail = f"Selected {_rule_label(winner)} as highest-ranked applicable rule."
    trace_steps: list[TraceStep] = [
        TraceStep(
            step_number=1,
            step_type="selection",
            action="selected",
            detail=winner_detail,
            rule_id=winner.id,
            rule_key=winner.rule_key,
            reason=None,
        )
    ]

    alt_labels: list[str] = []
    for idx, alt in enumerate(alternatives, start=2):
        reason_code, alt_detail = _alternative_loss_reason(winner, alt)
        trace_steps.append(
            TraceStep(
                step_number=idx,
                step_type="selection",
                action="not_selected",
                detail=alt_detail,
                rule_id=alt.id,
                rule_key=alt.rule_key,
                reason=reason_code,
            )
        )
        alt_labels.append(f"{_rule_label(alt)} [{reason_code}]")

    if alt_labels:
        explanation = (
            f"Selected {_rule_label(winner)}; non-selected alternatives: {'; '.join(alt_labels)}."
        )
    else:
        explanation = f"Selected {_rule_label(winner)}."

    return SelectionResult(
        winning_rule=winner,
        alternative_rules=alternatives,
        trace_steps=tuple(trace_steps),
        explanation=explanation,
    )


def create_no_applicable_rule_evaluation(
    card: CardContext,
    purchase: Purchase,
    message: str | None = None,
) -> CardEvaluation:
    """Create an ineligible CardEvaluation when no rule applies to the purchase.

    Per ARCHITECTURE §4.2 step 3:
    When no applicable rule remains (e.g., no base rule and no matching category/merchant rule),
    the card is ineligible with reason NO_APPLICABLE_RULE, 0 reward units, and an explanatory trace.
    """
    if message is not None and message.strip():
        explanation_text = message.strip()
    else:
        explanation_text = (
            f"No earning rules for '{card.card_name}' apply to category "
            f"'{purchase.category}' on {purchase.purchase_date.isoformat()}."
        )

    trace_step = TraceStep(
        step_number=1,
        step_type="selection",
        action="rejected",
        detail=explanation_text,
        reason=IneligibleReason.NO_APPLICABLE_RULE.value,
    )

    return CardEvaluation(
        card_id=card.card_id,
        card_name=card.card_name,
        reward_currency=card.reward_currency,
        status=CardStatus.INELIGIBLE,
        reward_units=Decimal("0"),
        estimated_value_cents=None,
        valuation_used=None,
        applied_portions=(),
        trace=(trace_step,),
        explanation=(explanation_text,),
        warnings=(),
        rejection_reason=IneligibleReason.NO_APPLICABLE_RULE.value,
        rejection_message=explanation_text,
    )
