"""Period boundary utilities for the reward engine (T13).

Computes inclusive start/end dates and the next reset date for MONTHLY,
QUARTERLY, CALENDAR_YEAR, and CARD_YEAR tracking periods.
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from app.engine.types import Period


@dataclass(frozen=True, slots=True)
class PeriodBounds:
    """Inclusive date bounds and next reset date for a tracking period."""

    start_date: date
    end_date: date
    next_reset_date: date

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if self.next_reset_date != self.end_date + timedelta(days=1):
            raise ValueError("next_reset_date must be the day immediately following end_date")


def _anniversary_in_year(opened_on: date, year: int) -> date:
    """Return the card-year anniversary date in a given calendar year.

    For February 29 openings, clamps to February 28 in non-leap years and uses
    February 29 in leap years.
    """
    if opened_on.month == 2 and opened_on.day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, opened_on.month, opened_on.day)


def get_period_bounds(
    period: Period,
    target_date: date,
    opened_on: date | None = None,
) -> PeriodBounds:
    """Compute inclusive period bounds and next reset date for target_date.

    Args:
        period: Tracking period type (MONTHLY, QUARTERLY, CALENDAR_YEAR, CARD_YEAR).
        target_date: Purchase or evaluation date.
        opened_on: Card open date, required when period is Period.CARD_YEAR.

    Returns:
        PeriodBounds with inclusive start_date/end_date and next_reset_date.
    """
    if period == Period.MONTHLY:
        start_date = date(target_date.year, target_date.month, 1)
        last_day = calendar.monthrange(target_date.year, target_date.month)[1]
        end_date = date(target_date.year, target_date.month, last_day)
        return PeriodBounds(
            start_date=start_date,
            end_date=end_date,
            next_reset_date=end_date + timedelta(days=1),
        )

    if period == Period.QUARTERLY:
        quarter_start_month = ((target_date.month - 1) // 3) * 3 + 1
        quarter_end_month = quarter_start_month + 2
        start_date = date(target_date.year, quarter_start_month, 1)
        last_day = calendar.monthrange(target_date.year, quarter_end_month)[1]
        end_date = date(target_date.year, quarter_end_month, last_day)
        return PeriodBounds(
            start_date=start_date,
            end_date=end_date,
            next_reset_date=end_date + timedelta(days=1),
        )

    if period == Period.CALENDAR_YEAR:
        start_date = date(target_date.year, 1, 1)
        end_date = date(target_date.year, 12, 31)
        return PeriodBounds(
            start_date=start_date,
            end_date=end_date,
            next_reset_date=end_date + timedelta(days=1),
        )

    if period == Period.CARD_YEAR:
        if opened_on is None:
            raise ValueError("opened_on is required for Period.CARD_YEAR")
        if target_date < opened_on:
            raise ValueError(
                f"target_date ({target_date.isoformat()}) cannot precede "
                f"opened_on ({opened_on.isoformat()})"
            )

        anniv_this_year = _anniversary_in_year(opened_on, target_date.year)
        if target_date >= anniv_this_year:
            start_date = anniv_this_year
            next_reset_date = _anniversary_in_year(opened_on, target_date.year + 1)
        else:
            start_date = _anniversary_in_year(opened_on, target_date.year - 1)
            next_reset_date = anniv_this_year

        return PeriodBounds(
            start_date=start_date,
            end_date=next_reset_date - timedelta(days=1),
            next_reset_date=next_reset_date,
        )

    raise ValueError(f"Unsupported period: {period}")
