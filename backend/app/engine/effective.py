"""Effective-date filtering for earning rules (T09, AC-6).

Pure date comparison logic determining which rule versions are active on a target date.
Contains no database, network, clock, or I/O side effects.
Target dates must be explicitly passed into functions.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.engine.types import (
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    IneligibleReason,
    TraceStep,
)


def is_rule_effective(rule: EarningRule, target_date: date) -> bool:
    """Return True if target_date falls within rule's inclusive effective range.

    The boundary semantics are inclusive on both ends:
    - effective_from <= target_date
    - effective_to is None or target_date <= effective_to
    """
    if target_date < rule.effective_from:
        return False
    return rule.effective_to is None or target_date <= rule.effective_to


def filter_effective_rules(
    rules: Sequence[EarningRule],
    target_date: date,
) -> tuple[EarningRule, ...]:
    """Filter earning rules effective on target_date, preserving input order."""
    return tuple(r for r in rules if is_rule_effective(r, target_date))


def create_no_effective_rule_evaluation(
    card: CardContext,
    target_date: date,
    message: str | None = None,
) -> CardEvaluation:
    """Create an ineligible CardEvaluation when a card has no rules effective on target_date.

    Per AC-6 and ARCHITECTURE §4.2 step 1:
    When no rule is effective, the card is ineligible with reason NO_EFFECTIVE_RULE,
    0 reward units, and an explanatory trace step and user-facing explanation message.
    """
    if message is not None and message.strip():
        explanation_text = message.strip()
    else:
        explanation_text = (
            f"No earning rules for '{card.card_name}' are effective on {target_date.isoformat()}."
        )

    trace_step = TraceStep(
        step_number=1,
        step_type="effective_filter",
        action="rejected",
        detail=explanation_text,
        reason=IneligibleReason.NO_EFFECTIVE_RULE.value,
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
        rejection_reason=IneligibleReason.NO_EFFECTIVE_RULE.value,
        rejection_message=explanation_text,
    )
