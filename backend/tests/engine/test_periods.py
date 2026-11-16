"""Table-driven unit tests for reward engine period boundaries (T13).

Validates MONTHLY, QUARTERLY, CALENDAR_YEAR, and CARD_YEAR boundary calculations,
including leap days (Feb 29), year-end transitions (Dec 31 / Jan 1), card-year
anniversary clamping, validation errors, and deterministic behavior.
"""

from datetime import date

import pytest

from app.engine.periods import PeriodBounds, get_period_bounds
from app.engine.types import Period


class TestMonthlyBounds:
    """Table-driven tests for Period.MONTHLY."""

    @pytest.mark.parametrize(
        ("target_date", "expected_start", "expected_end", "expected_reset"),
        [
            (date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 31), date(2026, 2, 1)),
            (date(2026, 1, 31), date(2026, 1, 1), date(2026, 1, 31), date(2026, 2, 1)),
            (date(2025, 2, 15), date(2025, 2, 1), date(2025, 2, 28), date(2025, 3, 1)),
            (date(2024, 2, 29), date(2024, 2, 1), date(2024, 2, 29), date(2024, 3, 1)),
            (date(2026, 4, 30), date(2026, 4, 1), date(2026, 4, 30), date(2026, 5, 1)),
            (date(2026, 12, 1), date(2026, 12, 1), date(2026, 12, 31), date(2027, 1, 1)),
            (date(2026, 12, 31), date(2026, 12, 1), date(2026, 12, 31), date(2027, 1, 1)),
        ],
    )
    def test_monthly_boundaries(
        self,
        target_date: date,
        expected_start: date,
        expected_end: date,
        expected_reset: date,
    ) -> None:
        bounds = get_period_bounds(Period.MONTHLY, target_date)

        assert bounds == PeriodBounds(
            start_date=expected_start,
            end_date=expected_end,
            next_reset_date=expected_reset,
        )


class TestQuarterlyBounds:
    """Table-driven tests for Period.QUARTERLY."""

    @pytest.mark.parametrize(
        ("target_date", "expected_start", "expected_end", "expected_reset"),
        [
            # Q1 (including leap year and non-leap year)
            (date(2026, 1, 1), date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1)),
            (date(2024, 2, 29), date(2024, 1, 1), date(2024, 3, 31), date(2024, 4, 1)),
            (date(2026, 3, 31), date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1)),
            # Q2
            (date(2026, 4, 1), date(2026, 4, 1), date(2026, 6, 30), date(2026, 7, 1)),
            (date(2026, 6, 30), date(2026, 4, 1), date(2026, 6, 30), date(2026, 7, 1)),
            # Q3
            (date(2026, 7, 1), date(2026, 7, 1), date(2026, 9, 30), date(2026, 10, 1)),
            (date(2026, 9, 30), date(2026, 7, 1), date(2026, 9, 30), date(2026, 10, 1)),
            # Q4 (including year-end rollover)
            (date(2026, 10, 1), date(2026, 10, 1), date(2026, 12, 31), date(2027, 1, 1)),
            (date(2026, 12, 31), date(2026, 10, 1), date(2026, 12, 31), date(2027, 1, 1)),
        ],
    )
    def test_quarterly_boundaries(
        self,
        target_date: date,
        expected_start: date,
        expected_end: date,
        expected_reset: date,
    ) -> None:
        bounds = get_period_bounds(Period.QUARTERLY, target_date)

        assert bounds == PeriodBounds(
            start_date=expected_start,
            end_date=expected_end,
            next_reset_date=expected_reset,
        )


class TestCalendarYearBounds:
    """Table-driven tests for Period.CALENDAR_YEAR."""

    @pytest.mark.parametrize(
        ("target_date", "expected_start", "expected_end", "expected_reset"),
        [
            (date(2026, 1, 1), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)),
            (date(2024, 2, 29), date(2024, 1, 1), date(2024, 12, 31), date(2025, 1, 1)),
            (date(2026, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)),
        ],
    )
    def test_calendar_year_boundaries(
        self,
        target_date: date,
        expected_start: date,
        expected_end: date,
        expected_reset: date,
    ) -> None:
        bounds = get_period_bounds(Period.CALENDAR_YEAR, target_date)

        assert bounds == PeriodBounds(
            start_date=expected_start,
            end_date=expected_end,
            next_reset_date=expected_reset,
        )


class TestCardYearBounds:
    """Table-driven tests for Period.CARD_YEAR anniversary boundaries."""

    @pytest.mark.parametrize(
        ("opened_on", "target_date", "expected_start", "expected_end", "expected_reset"),
        [
            # Standard mid-year opening
            (
                date(2024, 6, 15),
                date(2024, 6, 15),
                date(2024, 6, 15),
                date(2025, 6, 14),
                date(2025, 6, 15),
            ),
            (
                date(2024, 6, 15),
                date(2025, 6, 14),
                date(2024, 6, 15),
                date(2025, 6, 14),
                date(2025, 6, 15),
            ),
            (
                date(2024, 6, 15),
                date(2025, 6, 15),
                date(2025, 6, 15),
                date(2026, 6, 14),
                date(2026, 6, 15),
            ),
            # Year-end opening (Dec 31 -> Dec 30)
            (
                date(2025, 12, 31),
                date(2026, 1, 1),
                date(2025, 12, 31),
                date(2026, 12, 30),
                date(2026, 12, 31),
            ),
            (
                date(2025, 12, 31),
                date(2026, 12, 31),
                date(2026, 12, 31),
                date(2027, 12, 30),
                date(2027, 12, 31),
            ),
            # Jan 1 opening matches calendar year
            (
                date(2025, 1, 1),
                date(2025, 12, 31),
                date(2025, 1, 1),
                date(2025, 12, 31),
                date(2026, 1, 1),
            ),
            # Leap-day (Feb 29) opening across non-leap and leap years
            (
                date(2024, 2, 29),
                date(2024, 2, 29),
                date(2024, 2, 29),
                date(2025, 2, 27),
                date(2025, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2025, 2, 27),
                date(2024, 2, 29),
                date(2025, 2, 27),
                date(2025, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2025, 2, 28),
                date(2025, 2, 28),
                date(2026, 2, 27),
                date(2026, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2025, 3, 1),
                date(2025, 2, 28),
                date(2026, 2, 27),
                date(2026, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2026, 2, 27),
                date(2025, 2, 28),
                date(2026, 2, 27),
                date(2026, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2026, 2, 28),
                date(2026, 2, 28),
                date(2027, 2, 27),
                date(2027, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2026, 3, 1),
                date(2026, 2, 28),
                date(2027, 2, 27),
                date(2027, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2028, 2, 28),
                date(2027, 2, 28),
                date(2028, 2, 28),
                date(2028, 2, 29),
            ),
            (
                date(2024, 2, 29),
                date(2028, 2, 29),
                date(2028, 2, 29),
                date(2029, 2, 27),
                date(2029, 2, 28),
            ),
            (
                date(2024, 2, 29),
                date(2028, 3, 1),
                date(2028, 2, 29),
                date(2029, 2, 27),
                date(2029, 2, 28),
            ),
        ],
    )
    def test_card_year_boundaries(
        self,
        opened_on: date,
        target_date: date,
        expected_start: date,
        expected_end: date,
        expected_reset: date,
    ) -> None:
        bounds = get_period_bounds(Period.CARD_YEAR, target_date, opened_on=opened_on)

        assert bounds == PeriodBounds(
            start_date=expected_start,
            end_date=expected_end,
            next_reset_date=expected_reset,
        )

    def test_card_year_requires_opened_on(self) -> None:
        with pytest.raises(ValueError, match="opened_on"):
            get_period_bounds(Period.CARD_YEAR, date(2026, 5, 1), opened_on=None)

    def test_card_year_rejects_target_before_opened_on(self) -> None:
        with pytest.raises(ValueError, match="precede"):
            get_period_bounds(
                Period.CARD_YEAR,
                date(2026, 5, 1),
                opened_on=date(2026, 5, 2),
            )


class TestPeriodDeterminismAndImmutability:
    """Tests for PeriodBounds determinism and frozen immutability."""

    def test_repeated_calls_are_deterministic(self) -> None:
        first = get_period_bounds(Period.CARD_YEAR, date(2025, 3, 15), opened_on=date(2024, 2, 29))
        second = get_period_bounds(Period.CARD_YEAR, date(2025, 3, 15), opened_on=date(2024, 2, 29))
        assert first == second

    def test_period_bounds_is_frozen(self) -> None:
        bounds = get_period_bounds(Period.MONTHLY, date(2026, 11, 15))
        with pytest.raises(AttributeError):
            bounds.end_date = date(2026, 12, 1)  # type: ignore[misc]

    def test_period_bounds_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="end_date cannot precede start_date"):
            PeriodBounds(
                start_date=date(2026, 2, 10),
                end_date=date(2026, 2, 9),
                next_reset_date=date(2026, 2, 10),
            )

    def test_period_bounds_rejects_invalid_next_reset_date(self) -> None:
        with pytest.raises(ValueError, match="next_reset_date"):
            PeriodBounds(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 28),
                next_reset_date=date(2026, 2, 28),
            )

    def test_unsupported_period_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported period"):
            get_period_bounds("weekly", date(2026, 1, 1))  # type: ignore[arg-type]
