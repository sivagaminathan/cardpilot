"""Cap handling, straddle splitting, and fallback allocation (T14, AC-5).

Allocates a purchase amount across capped and uncapped earning rules by
iteratively selecting the best applicable rule whose cap group is not
exhausted, allocating up to the remaining cap, and falling back to the next
eligible rule when a cap is exhausted or straddled.

Does not compute or round reward units (handled separately in T16).
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.engine.applicability import filter_applicable_rules
from app.engine.selection import select_best_rule
from app.engine.types import (
    EarningRule,
    Purchase,
    SpendCap,
    SpendHistory,
    TraceStep,
    _normalize_sequence,
    _validate_cents,
)


def _format_cents(cents: int) -> str:
    """Format integer cents as dollars and cents without floating-point arithmetic."""
    dollars, rem = divmod(cents, 100)
    return f"${dollars}.{rem:02d} ({cents} cents)"


@dataclass(frozen=True, slots=True)
class CapPortion:
    """A portion of a purchase allocated to a single earning rule."""

    rule: EarningRule
    amount_cents: int
    cap_group_key: str | None = None

    def __post_init__(self) -> None:
        _validate_cents(self.amount_cents, "amount_cents")


@dataclass(frozen=True, slots=True)
class CapAllocationResult:
    """Result of allocating a purchase across spend caps and fallback rules."""

    portions: Sequence[CapPortion]
    unallocated_cents: int = 0
    trace_steps: Sequence[TraceStep] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.unallocated_cents, int)
            or isinstance(self.unallocated_cents, bool)
            or self.unallocated_cents < 0
        ):
            raise ValueError(
                f"unallocated_cents must be a non-negative integer, got {self.unallocated_cents!r}"
            )
        object.__setattr__(
            self,
            "portions",
            _normalize_sequence(self.portions, "portions"),
        )
        object.__setattr__(
            self,
            "trace_steps",
            _normalize_sequence(self.trace_steps, "trace_steps"),
        )


def _build_cap_map(caps: Sequence[SpendCap]) -> dict[str, SpendCap]:
    """Index SpendCap entries by cap_group_key, rejecting duplicates."""
    cap_map: dict[str, SpendCap] = {}
    for cap in caps:
        if cap.cap_group_key in cap_map:
            raise ValueError(f"Duplicate cap_group_key {cap.cap_group_key!r} in caps")
        cap_map[cap.cap_group_key] = cap
    return cap_map


def allocate_purchase_across_caps(
    purchase: Purchase,
    rules: Sequence[EarningRule],
    caps: Sequence[SpendCap],
    spend_history: SpendHistory,
) -> CapAllocationResult:
    """Allocate purchase.amount_cents across applicable rules and spend caps.

    Iteratively:
    1. Filters rules excluding already-exhausted cap groups.
    2. Reruns applicability filtering and deterministic rule selection.
    3. Allocates up to remaining cap capacity, or the full remaining purchase
       amount if uncapped.
    4. Continues with the remaining purchase amount if the cap is straddled or
       already exhausted.
    5. Records any unallocated remainder if no eligible fallback rule exists.
    """
    cap_map = _build_cap_map(caps)
    initial_applicable_rules, _ = filter_applicable_rules(rules, purchase)
    for rule in initial_applicable_rules:
        if rule.cap_group_key is not None and rule.cap_group_key not in cap_map:
            raise ValueError(
                f"Rule '{rule.rule_key}' (id={rule.id}) references unknown "
                f"cap_group_key '{rule.cap_group_key}'."
            )

    remaining_amount_cents = purchase.amount_cents
    exhausted_cap_groups: set[str] = set()
    portions: list[CapPortion] = []
    traces: list[TraceStep] = []
    step_num = 1

    while remaining_amount_cents > 0:
        candidate_rules = tuple(
            r
            for r in initial_applicable_rules
            if r.cap_group_key is None or r.cap_group_key not in exhausted_cap_groups
        )
        selection = select_best_rule(candidate_rules)

        if selection is None:
            traces.append(
                TraceStep(
                    step_number=step_num,
                    step_type="cap_allocation",
                    action="unallocated",
                    reason="no_fallback_rule",
                    detail=(
                        f"No eligible fallback rule remains for unallocated amount "
                        f"{_format_cents(remaining_amount_cents)}."
                    ),
                )
            )
            break

        winner = selection.winning_rule

        if winner.cap_group_key is None:
            portions.append(
                CapPortion(
                    rule=winner,
                    amount_cents=remaining_amount_cents,
                    cap_group_key=None,
                )
            )
            traces.append(
                TraceStep(
                    step_number=step_num,
                    step_type="cap_allocation",
                    action="allocated",
                    rule_id=winner.id,
                    rule_key=winner.rule_key,
                    detail=(
                        f"Allocated {_format_cents(remaining_amount_cents)} to uncapped "
                        f"rule '{winner.rule_key}' ({winner.multiplier}x)."
                    ),
                )
            )
            remaining_amount_cents = 0
            break

        cap = cap_map.get(winner.cap_group_key)
        if cap is None:
            raise ValueError(
                f"Rule '{winner.rule_key}' (id={winner.id}) references unknown "
                f"cap_group_key '{winner.cap_group_key}'."
            )

        prior_spend = spend_history.get_cap_spend(winner.cap_group_key)
        cap_remaining = max(0, cap.cap_amount_cents - prior_spend)

        if cap_remaining == 0:
            exhausted_cap_groups.add(winner.cap_group_key)
            traces.append(
                TraceStep(
                    step_number=step_num,
                    step_type="cap_allocation",
                    action="cap_exhausted",
                    rule_id=winner.id,
                    rule_key=winner.rule_key,
                    reason="cap_exhausted",
                    detail=(
                        f"Cap group '{winner.cap_group_key}' for rule '{winner.rule_key}' "
                        f"is exhausted (cap {_format_cents(cap.cap_amount_cents)}, "
                        f"prior spend {_format_cents(prior_spend)})."
                    ),
                )
            )
            step_num += 1
            continue

        allocated_cents = min(remaining_amount_cents, cap_remaining)
        portions.append(
            CapPortion(
                rule=winner,
                amount_cents=allocated_cents,
                cap_group_key=winner.cap_group_key,
            )
        )
        traces.append(
            TraceStep(
                step_number=step_num,
                step_type="cap_allocation",
                action="allocated",
                rule_id=winner.id,
                rule_key=winner.rule_key,
                detail=(
                    f"Allocated {_format_cents(allocated_cents)} to rule "
                    f"'{winner.rule_key}' ({winner.multiplier}x) under cap group "
                    f"'{winner.cap_group_key}' (remaining before purchase: "
                    f"{_format_cents(cap_remaining)})."
                ),
            )
        )
        remaining_amount_cents -= allocated_cents
        step_num += 1

        if remaining_amount_cents > 0:
            exhausted_cap_groups.add(winner.cap_group_key)

    return CapAllocationResult(
        portions=tuple(portions),
        unallocated_cents=remaining_amount_cents,
        trace_steps=tuple(traces),
    )
