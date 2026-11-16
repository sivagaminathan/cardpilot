"""Per-card purchase evaluation orchestrator (T20, ARCHITECTURE §4.1-4.2).

Composes the pure engine stages in documented order:
1. Effective-date filter
2. Applicability filter (scope, exclusions, min tx, period spend)
3. Deterministic rule selection
4. Cap allocation and iterative fallback
5. Reward unit calculation and transaction-level rounding
6. Valuation or no-valuation routing
7. Structured trace assembly and sentence explanation rendering

Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal

from app.engine.applicability import filter_applicable_rules
from app.engine.caps import allocate_purchase_across_caps
from app.engine.effective import (
    create_no_effective_rule_evaluation,
    filter_effective_rules,
)
from app.engine.explain import render_explanation
from app.engine.selection import (
    create_no_applicable_rule_evaluation,
    select_best_rule,
)
from app.engine.types import (
    CardContext,
    CardEvaluation,
    CardStatus,
    IneligibleReason,
    Purchase,
    SpendHistory,
    TraceStep,
    Valuation,
)
from app.engine.units import calculate_reward_units
from app.engine.valuation import evaluate_valuation


def _renumber_trace(steps: Sequence[TraceStep]) -> tuple[TraceStep, ...]:
    """Assign deterministic 1-based step_number across combined pipeline stages."""
    return tuple(replace(step, step_number=idx) for idx, step in enumerate(steps, start=1))


def evaluate_purchase(
    purchase: Purchase,
    card: CardContext,
    spend_history: SpendHistory,
    valuation: Valuation | None,
) -> CardEvaluation:
    """Evaluate a single card's reward outcome for a purchase.

    Composes effective filtering, applicability filtering, rule selection,
    cap allocation, unit calculation/rounding, valuation, and explanation
    rendering into an immutable CardEvaluation.
    """
    effective_rules = filter_effective_rules(card.rules, purchase.purchase_date)
    if not effective_rules:
        no_eff = create_no_effective_rule_evaluation(card, purchase.purchase_date)
        return replace(no_eff, explanation=render_explanation(no_eff.trace))

    applicable_rules, app_traces = filter_applicable_rules(
        effective_rules, purchase, spend_history=spend_history
    )
    if not applicable_rules:
        no_app = create_no_applicable_rule_evaluation(card, purchase)
        combined = _renumber_trace((*app_traces, *no_app.trace))
        return replace(no_app, trace=combined, explanation=render_explanation(combined))

    selection = select_best_rule(applicable_rules)
    if selection is None:  # pragma: no cover - guarded by non-empty applicable_rules
        no_app = create_no_applicable_rule_evaluation(card, purchase)
        combined = _renumber_trace((*app_traces, *no_app.trace))
        return replace(no_app, trace=combined, explanation=render_explanation(combined))

    cap_res = allocate_purchase_across_caps(purchase, applicable_rules, card.caps, spend_history)
    if not cap_res.portions:
        combined = _renumber_trace((*app_traces, *selection.trace_steps, *cap_res.trace_steps))
        explanation = render_explanation(combined)
        return CardEvaluation(
            card_id=card.card_id,
            card_name=card.card_name,
            reward_currency=card.reward_currency,
            status=CardStatus.INELIGIBLE,
            reward_units=Decimal("0"),
            estimated_value_cents=None,
            valuation_used=None,
            applied_portions=(),
            trace=combined,
            explanation=explanation,
            warnings=(),
            rejection_reason=IneligibleReason.NO_APPLICABLE_RULE.value,
            rejection_message=explanation[-1] if explanation else "All applicable caps exhausted.",
        )

    units_res = calculate_reward_units(cap_res.portions)
    val_res = evaluate_valuation(units_res.total_reward_units, card.reward_currency, valuation)

    combined_trace = _renumber_trace(
        (
            *app_traces,
            *selection.trace_steps,
            *cap_res.trace_steps,
            units_res.trace_step,
            val_res.trace_step,
        )
    )
    explanation = render_explanation(combined_trace)

    return CardEvaluation(
        card_id=card.card_id,
        card_name=card.card_name,
        reward_currency=card.reward_currency,
        status=val_res.status,
        reward_units=units_res.total_reward_units,
        estimated_value_cents=val_res.estimated_value_cents,
        valuation_used=val_res.valuation_used,
        applied_portions=units_res.applied_portions,
        trace=combined_trace,
        explanation=explanation,
        warnings=val_res.warnings,
        rejection_reason=val_res.rejection_reason,
        rejection_message=val_res.rejection_message,
    )
