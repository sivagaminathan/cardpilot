"""Unit tests for cross-card ranking, tie-breaking, and global notes (T18, AC-2, AC-10).

Validates partitioning by CardStatus, descending estimated_value_cents ranking,
reward_units/nickname/card_id tie-breaking, tie explanation injection via
replacement instances, deterministic ordering of unranked/ineligible cards,
global notes for mixed/all-unranked/all-ineligible/empty inputs, immutability,
and determinism.
"""

from decimal import Decimal

import pytest

from app.engine.ranking import (
    GLOBAL_COMPARISON_NOTE,
    NO_RANKABLE_CARDS_NOTE,
    RankingResult,
    rank_card_evaluations,
)
from app.engine.types import (
    CardEvaluation,
    CardStatus,
    IneligibleReason,
    UnrankedReason,
    Valuation,
)


def _make_ranked(
    card_id: int,
    card_name: str,
    estimated_value_cents: int,
    reward_units: str = "100",
    reward_currency: str = "POINTS",
    explanation: tuple[str, ...] = ("Matched base rule.",),
) -> CardEvaluation:
    return CardEvaluation(
        card_id=card_id,
        card_name=card_name,
        reward_currency=reward_currency,
        status=CardStatus.RANKED,
        reward_units=Decimal(reward_units),
        estimated_value_cents=estimated_value_cents,
        valuation_used=Valuation(reward_currency, Decimal("1.0"), is_user_set=True),
        explanation=explanation,
    )


def _make_unranked(
    card_id: int,
    card_name: str,
    reward_units: str = "5000",
    reward_currency: str = "SKY_MILES",
) -> CardEvaluation:
    return CardEvaluation(
        card_id=card_id,
        card_name=card_name,
        reward_currency=reward_currency,
        status=CardStatus.UNRANKED,
        reward_units=Decimal(reward_units),
        estimated_value_cents=None,
        rejection_reason=UnrankedReason.NO_VALUATION.value,
        rejection_message=(
            f"No estimated value is set for {reward_currency}, so this card cannot be "
            "reliably compared in dollars. Set a valuation in Settings."
        ),
    )


def _make_ineligible(
    card_id: int,
    card_name: str,
    reason: IneligibleReason = IneligibleReason.NO_APPLICABLE_RULE,
) -> CardEvaluation:
    return CardEvaluation(
        card_id=card_id,
        card_name=card_name,
        reward_currency="CASH_USD",
        status=CardStatus.INELIGIBLE,
        reward_units=Decimal("0"),
        estimated_value_cents=None,
        rejection_reason=reason.value,
        rejection_message="No rule applied.",
    )


class TestCrossCardRanking:
    """Tests for partitioning, ranked sort order, and tie handling."""

    def test_partitioning_and_descending_estimated_value(self) -> None:
        c_low = _make_ranked(1, "Alpha Cash", estimated_value_cents=150, reward_units="150")
        c_high = _make_ranked(2, "Beta Points", estimated_value_cents=450, reward_units="300")
        c_unranked = _make_unranked(3, "Gamma Miles", reward_units="99999")
        c_ineligible = _make_ineligible(4, "Delta Card")

        result = rank_card_evaluations((c_low, c_ineligible, c_unranked, c_high))

        assert isinstance(result, RankingResult)
        assert [c.card_id for c in result.ranked] == [2, 1]
        assert [c.card_id for c in result.unranked] == [3]
        assert [c.card_id for c in result.ineligible] == [4]
        assert result.global_notes == (GLOBAL_COMPARISON_NOTE,)
        # No tie explanation when estimated values differ
        assert all(
            "tied on estimated value" not in line.casefold()
            for line in result.ranked[0].explanation
        )
        assert all(
            "tied on estimated value" not in line.casefold()
            for line in result.ranked[1].explanation
        )

    def test_tie_break_by_reward_units_nickname_and_card_id(self) -> None:
        # All 4 cards tie at 300 cents:
        # - Card 10: 400 units -> 1st
        # - Card 20: 200 units, name "alpha" -> 2nd (case-insensitive nickname)
        # - Card 30: 200 units, name "Beta", id=30 -> 3rd (same units, later nickname)
        # - Card 25: 200 units, name "Beta", id=25 -> 3rd? Wait: id=25 < id=30 -> 25 before 30!
        c_units = _make_ranked(
            10, "Zeta", estimated_value_cents=300, reward_units="400", explanation=("Base 4x.",)
        )
        c_alpha = _make_ranked(
            20, "alpha", estimated_value_cents=300, reward_units="200", explanation=("Base 2x.",)
        )
        c_beta_30 = _make_ranked(
            30, "Beta", estimated_value_cents=300, reward_units="200", explanation=("Base 2x.",)
        )
        c_beta_25 = _make_ranked(
            25, "Beta", estimated_value_cents=300, reward_units="200", explanation=("Base 2x.",)
        )
        c_other = _make_ranked(
            40, "Other", estimated_value_cents=100, reward_units="100", explanation=("Base 1x.",)
        )

        result = rank_card_evaluations((c_beta_30, c_other, c_alpha, c_beta_25, c_units))

        assert [c.card_id for c in result.ranked] == [10, 20, 25, 30, 40]

        # Every member of the 300-cent tie group has "tied on estimated value" appended
        for tied_card in result.ranked[:4]:
            assert tied_card.explanation[0].startswith("Base")
            assert any(
                "tied on estimated value" in line.casefold() for line in tied_card.explanation
            )

        # Non-tied 100-cent card does NOT get tie explanation
        assert result.ranked[4].explanation == ("Base 1x.",)
        # Original input instances remain unmutated
        assert c_units.explanation == ("Base 4x.",)


class TestUnrankedIneligibleAndGlobalNotes:
    """Tests for deterministic unranked/ineligible ordering and global notes."""

    def test_unranked_and_ineligible_sort_by_nickname_then_id_never_raw_units(self) -> None:
        # Unranked card with lower units (100) but earlier nickname "alpha" precedes "Zeta"
        u_zeta = _make_unranked(1, "Zeta Miles", reward_units="99999")
        u_alpha = _make_unranked(2, "alpha Miles", reward_units="100")
        u_beta_2 = _make_unranked(5, "Beta Miles", reward_units="500")
        u_beta_1 = _make_unranked(4, "Beta Miles", reward_units="10")

        i_zeta = _make_ineligible(10, "Zeta Ineligible")
        i_alpha = _make_ineligible(11, "alpha Ineligible")

        result = rank_card_evaluations((u_zeta, u_beta_2, u_alpha, u_beta_1, i_zeta, i_alpha))

        assert [c.card_id for c in result.unranked] == [2, 4, 5, 1]
        assert [c.card_id for c in result.ineligible] == [11, 10]
        assert result.unranked[0].rejection_reason == UnrankedReason.NO_VALUATION.value
        assert result.ineligible[0].rejection_reason == IneligibleReason.NO_APPLICABLE_RULE.value

    def test_global_notes_for_all_unranked_all_ineligible_and_empty_inputs(self) -> None:
        # All unranked -> includes limitation note
        res_unranked = rank_card_evaluations((_make_unranked(1, "Miles"),))
        assert res_unranked.global_notes == (GLOBAL_COMPARISON_NOTE, NO_RANKABLE_CARDS_NOTE)

        # All ineligible -> no rankable cards -> includes limitation note
        res_ineligible = rank_card_evaluations((_make_ineligible(2, "Ineligible"),))
        assert res_ineligible.global_notes == (GLOBAL_COMPARISON_NOTE, NO_RANKABLE_CARDS_NOTE)

        # Empty input -> standard note only, does not claim cards were evaluated
        res_empty = rank_card_evaluations(())
        assert res_empty.ranked == ()
        assert res_empty.unranked == ()
        assert res_empty.ineligible == ()
        assert res_empty.global_notes == (GLOBAL_COMPARISON_NOTE,)


class TestValidationImmutabilityAndDeterminism:
    """Tests for inconsistent status/value rejection, immutability, and determinism."""

    def test_inconsistent_card_evaluation_rejected(self) -> None:
        # Construct an inconsistent CardEvaluation bypassing __post_init__
        bad_ranked = _make_ranked(1, "Bad", estimated_value_cents=100)
        object.__setattr__(bad_ranked, "estimated_value_cents", None)
        with pytest.raises(ValueError, match="estimated_value_cents"):
            rank_card_evaluations((bad_ranked,))

        bad_unranked = _make_unranked(2, "Bad Unranked")
        object.__setattr__(bad_unranked, "estimated_value_cents", 200)
        with pytest.raises(ValueError, match="estimated_value_cents"):
            rank_card_evaluations((bad_unranked,))

    def test_determinism_and_immutability(self) -> None:
        c1 = _make_ranked(1, "Alpha", estimated_value_cents=200, reward_units="200")
        c2 = _make_ranked(2, "Beta", estimated_value_cents=200, reward_units="100")
        u1 = _make_unranked(3, "Gamma")

        r1 = rank_card_evaluations((c1, u1, c2))
        r2 = rank_card_evaluations((c2, c1, u1))

        assert r1 == r2
        with pytest.raises(AttributeError):
            r1.ranked = ()  # type: ignore[misc]
        with pytest.raises(TypeError, match="set"):
            rank_card_evaluations({c1})  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="set"):
            RankingResult(ranked={c1}, unranked=(), ineligible=(), global_notes=())  # type: ignore[arg-type]
