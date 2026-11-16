"""Rule applicability, exclusion, and threshold evaluation (T10, T12, T15, AC-4, AC-7).

Determines whether earning rules match a purchase context by scope (BASE, CATEGORY, MERCHANT),
evaluates rule exclusions (category, merchant, merchant_tag) with case/whitespace normalization,
enforces per-transaction minimum spend thresholds (min_transaction_cents), and enforces
non-retroactive period-spend thresholds (min_period_spend_cents / threshold_period).
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.engine.types import (
    EarningRule,
    ExclusionType,
    Purchase,
    RuleExclusion,
    ScopeType,
    SpendHistory,
    TraceStep,
)


@dataclass(frozen=True, slots=True)
class ApplicabilityResult:
    """Evaluation outcome of a rule's applicability to a purchase."""

    is_applicable: bool
    rejection_reason: str | None = None
    rejection_detail: str | None = None
    matched_exclusion: RuleExclusion | None = None


def _normalize(value: str) -> str:
    """Normalize a string for case-insensitive, whitespace-trimmed comparison."""
    return value.strip().casefold()


def _matches_scope(rule: EarningRule, purchase: Purchase) -> tuple[bool, str | None, str | None]:
    """Check if purchase matches rule scope.

    Returns:
        (matches, rejection_reason, rejection_detail)
    """
    if rule.scope_type == ScopeType.BASE:
        return True, None, None

    if rule.scope_type == ScopeType.CATEGORY:
        if rule.category is not None and _normalize(rule.category) == _normalize(purchase.category):
            return True, None, None
        return (
            False,
            "category_mismatch",
            f"Purchase category '{purchase.category}' does not match rule category "
            f"'{rule.category}'.",
        )

    if rule.scope_type == ScopeType.MERCHANT:
        if purchase.merchant is None:
            return (
                False,
                "missing_merchant",
                f"Rule requires merchant '{rule.merchant}', but purchase has no "
                "merchant specified.",
            )
        if rule.merchant is not None and _normalize(rule.merchant) == _normalize(purchase.merchant):
            return True, None, None
        return (
            False,
            "merchant_mismatch",
            f"Purchase merchant '{purchase.merchant}' does not match rule merchant "
            f"'{rule.merchant}'.",
        )

    return False, "unknown_scope", f"Unknown scope type: {rule.scope_type}"


def _find_matching_exclusion(
    rule: EarningRule,
    purchase: Purchase,
) -> tuple[RuleExclusion | None, str | None, str | None]:
    """Check if any exclusion on the rule matches the purchase context.

    Returns:
        (matched_exclusion, rejection_reason, rejection_detail)
    """
    for exclusion in rule.exclusions:
        target_norm = _normalize(exclusion.target)
        if not target_norm:
            continue

        if exclusion.exclusion_type == ExclusionType.CATEGORY:
            if _normalize(purchase.category) == target_norm:
                return (
                    exclusion,
                    "category_exclusion",
                    f"Purchase category '{purchase.category}' is excluded: {exclusion.reason}",
                )

        elif exclusion.exclusion_type == ExclusionType.MERCHANT:
            if purchase.merchant is not None and _normalize(purchase.merchant) == target_norm:
                return (
                    exclusion,
                    "merchant_exclusion",
                    f"Purchase merchant '{purchase.merchant}' is excluded: {exclusion.reason}",
                )

        elif exclusion.exclusion_type == ExclusionType.MERCHANT_TAG:
            for tag in purchase.merchant_tags:
                tag_norm = _normalize(tag)
                if tag_norm and tag_norm == target_norm:
                    return (
                        exclusion,
                        "merchant_tag_exclusion",
                        f"Purchase merchant tag '{tag}' is excluded: {exclusion.reason}",
                    )

    return None, None, None


def _format_cents(cents: int) -> str:
    """Format integer cents as dollars and cents without floating-point arithmetic."""
    dollars, rem = divmod(cents, 100)
    return f"${dollars}.{rem:02d} ({cents} cents)"


def _check_min_transaction_threshold(
    rule: EarningRule,
    purchase: Purchase,
) -> tuple[bool, str | None, str | None]:
    """Check if purchase meets the rule's per-transaction minimum threshold.

    Returns:
        (passes, rejection_reason, rejection_detail)
    """
    if rule.min_transaction_cents is None:
        return True, None, None

    if purchase.amount_cents >= rule.min_transaction_cents:
        return True, None, None

    return (
        False,
        "below_min_transaction",
        f"Purchase amount {_format_cents(purchase.amount_cents)} is below rule "
        f"minimum transaction threshold of {_format_cents(rule.min_transaction_cents)}.",
    )


def _check_period_spend_threshold(
    rule: EarningRule,
    spend_history: SpendHistory | None,
) -> tuple[bool, str | None, str | None]:
    """Check if prior period spend meets the rule's non-retroactive period threshold.

    Returns:
        (passes, rejection_reason, rejection_detail)
    """
    if (rule.min_period_spend_cents is None) != (rule.threshold_period is None):
        raise ValueError(
            f"Rule '{rule.rule_key}' (id={rule.id}) must configure both "
            "min_period_spend_cents and threshold_period together, or leave both None."
        )

    if rule.min_period_spend_cents is None or rule.threshold_period is None:
        return True, None, None

    if spend_history is None:
        raise ValueError(
            f"spend_history is required when rule '{rule.rule_key}' (id={rule.id}) "
            "configures a period-spend threshold."
        )

    prior_spend_cents = spend_history.get_threshold_spend(rule.threshold_period.value)
    if prior_spend_cents >= rule.min_period_spend_cents:
        return True, None, None

    return (
        False,
        "below_min_period_spend",
        f"Prior {rule.threshold_period.value} spend {_format_cents(prior_spend_cents)} "
        f"is below rule period-spend threshold of "
        f"{_format_cents(rule.min_period_spend_cents)}.",
    )


def check_rule_applicability(
    rule: EarningRule,
    purchase: Purchase,
    spend_history: SpendHistory | None = None,
) -> ApplicabilityResult:
    """Evaluate whether a rule applies to a purchase context.

    Scope matching is checked first, followed by exclusions in order,
    per-transaction minimum threshold, and non-retroactive period-spend threshold.
    Returns ApplicabilityResult with stable rejection reason and detail on rejection.
    """
    scope_matches, scope_reason, scope_detail = _matches_scope(rule, purchase)
    if not scope_matches:
        return ApplicabilityResult(
            is_applicable=False,
            rejection_reason=scope_reason,
            rejection_detail=scope_detail,
        )

    matched_ex, ex_reason, ex_detail = _find_matching_exclusion(rule, purchase)
    if matched_ex is not None:
        return ApplicabilityResult(
            is_applicable=False,
            rejection_reason=ex_reason,
            rejection_detail=ex_detail,
            matched_exclusion=matched_ex,
        )

    meets_min, min_reason, min_detail = _check_min_transaction_threshold(rule, purchase)
    if not meets_min:
        return ApplicabilityResult(
            is_applicable=False,
            rejection_reason=min_reason,
            rejection_detail=min_detail,
        )

    meets_period, period_reason, period_detail = _check_period_spend_threshold(rule, spend_history)
    if not meets_period:
        return ApplicabilityResult(
            is_applicable=False,
            rejection_reason=period_reason,
            rejection_detail=period_detail,
        )

    return ApplicabilityResult(is_applicable=True)


def filter_applicable_rules(
    rules: Sequence[EarningRule],
    purchase: Purchase,
    spend_history: SpendHistory | None = None,
) -> tuple[tuple[EarningRule, ...], tuple[TraceStep, ...]]:
    """Filter applicable rules and generate rejection trace steps in deterministic input order."""
    applicable: list[EarningRule] = []
    traces: list[TraceStep] = []
    rejection_step_num = 1

    for rule in rules:
        result = check_rule_applicability(rule, purchase, spend_history=spend_history)
        if result.is_applicable:
            applicable.append(rule)
        else:
            trace = TraceStep(
                step_number=rejection_step_num,
                step_type="applicability_filter",
                action="rejected",
                detail=result.rejection_detail or "",
                rule_id=rule.id,
                rule_key=rule.rule_key,
                reason=result.rejection_reason,
            )
            traces.append(trace)
            rejection_step_num += 1

    return tuple(applicable), tuple(traces)
