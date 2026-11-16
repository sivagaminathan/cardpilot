"""Cross-card ranking, tie-breaking, and global notes (T18, AC-2, AC-10).

Partitions per-card CardEvaluation results into ranked, unranked, and ineligible
buckets, sorts ranked cards deterministically by estimated USD cents descending
with tie-breaking, appends tie explanations, and emits immutable global notes.
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from app.engine.types import (
    CardEvaluation,
    CardStatus,
    _normalize_sequence,
)

GLOBAL_COMPARISON_NOTE = "Annual fees and benefit credits are not included in this comparison."
NO_RANKABLE_CARDS_NOTE = "No cards can be ranked because none has an available estimated value."
_TIED_EXPLANATION = "Tied on estimated value."


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Immutable cross-card ranking result partitioned by CardStatus."""

    ranked: Sequence[CardEvaluation]
    unranked: Sequence[CardEvaluation]
    ineligible: Sequence[CardEvaluation]
    global_notes: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ranked", _normalize_sequence(self.ranked, "ranked"))
        object.__setattr__(self, "unranked", _normalize_sequence(self.unranked, "unranked"))
        object.__setattr__(self, "ineligible", _normalize_sequence(self.ineligible, "ineligible"))
        object.__setattr__(
            self, "global_notes", _normalize_sequence(self.global_notes, "global_notes")
        )


def _validate_evaluation(evaluation: CardEvaluation) -> None:
    """Verify CardStatus and estimated_value_cents consistency."""
    if evaluation.status == CardStatus.RANKED:
        if evaluation.estimated_value_cents is None:
            raise ValueError(
                f"Ranked card '{evaluation.card_name}' (id={evaluation.card_id}) "
                "must have estimated_value_cents."
            )
    elif evaluation.status in (CardStatus.UNRANKED, CardStatus.INELIGIBLE):
        if evaluation.estimated_value_cents is not None:
            raise ValueError(
                f"{evaluation.status.value} card '{evaluation.card_name}' "
                f"(id={evaluation.card_id}) cannot have estimated_value_cents."
            )
    else:
        raise ValueError(f"Unsupported CardStatus: {evaluation.status!r}")


def _ranked_sort_key(evaluation: CardEvaluation) -> tuple[int, Decimal, str, str, int]:
    """Sort key for ranked cards: value desc, reward_units desc, nickname asc, id asc."""
    if evaluation.estimated_value_cents is None:
        raise ValueError("Ranked evaluation missing estimated_value_cents")
    return (
        -evaluation.estimated_value_cents,
        -evaluation.reward_units,
        evaluation.card_name.casefold(),
        evaluation.card_name,
        evaluation.card_id,
    )


def _non_ranked_sort_key(evaluation: CardEvaluation) -> tuple[str, str, int]:
    """Deterministic sort key for unranked and ineligible cards."""
    return (
        evaluation.card_name.casefold(),
        evaluation.card_name,
        evaluation.card_id,
    )


def _apply_tie_explanations(ranked: Sequence[CardEvaluation]) -> tuple[CardEvaluation, ...]:
    """Annotate every card in a tied estimated_value_cents group via replacement."""
    counts: Counter[int] = Counter()
    for ev in ranked:
        if ev.estimated_value_cents is not None:
            counts[ev.estimated_value_cents] += 1

    annotated: list[CardEvaluation] = []
    for ev in ranked:
        if ev.estimated_value_cents is not None and counts[ev.estimated_value_cents] > 1:
            already_noted = any(
                "tied on estimated value" in line.casefold() for line in ev.explanation
            )
            if not already_noted:
                annotated.append(replace(ev, explanation=(*ev.explanation, _TIED_EXPLANATION)))
            else:
                annotated.append(ev)
        else:
            annotated.append(ev)
    return tuple(annotated)


def rank_card_evaluations(evaluations: Sequence[CardEvaluation]) -> RankingResult:
    """Partition and deterministically rank card evaluations across currencies.

    Ranked cards are sorted by estimated_value_cents desc, reward_units desc,
    card_name.casefold() asc, card_name asc, card_id asc.
    Unranked and ineligible cards are sorted by card_name.casefold() asc,
    card_name asc, card_id asc.
    """
    normalized = _normalize_sequence(evaluations, "evaluations")

    ranked_list: list[CardEvaluation] = []
    unranked_list: list[CardEvaluation] = []
    ineligible_list: list[CardEvaluation] = []

    for ev in normalized:
        _validate_evaluation(ev)
        if ev.status == CardStatus.RANKED:
            ranked_list.append(ev)
        elif ev.status == CardStatus.UNRANKED:
            unranked_list.append(ev)
        elif ev.status == CardStatus.INELIGIBLE:
            ineligible_list.append(ev)

    ranked_sorted = sorted(ranked_list, key=_ranked_sort_key)
    ranked_final = _apply_tie_explanations(ranked_sorted)
    unranked_final = tuple(sorted(unranked_list, key=_non_ranked_sort_key))
    ineligible_final = tuple(sorted(ineligible_list, key=_non_ranked_sort_key))

    notes: list[str] = [GLOBAL_COMPARISON_NOTE]
    if normalized and not ranked_final:
        notes.append(NO_RANKABLE_CARDS_NOTE)

    return RankingResult(
        ranked=ranked_final,
        unranked=unranked_final,
        ineligible=ineligible_final,
        global_notes=tuple(notes),
    )
