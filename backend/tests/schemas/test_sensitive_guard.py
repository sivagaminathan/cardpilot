"""Unit tests for the shared sensitive-data digit sequence guard (T30, AC-12)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.validators import (
    SafeFreeText,
    contains_sensitive_digit_sequence,
    validate_no_sensitive_digits,
)


class _DummyPayload(BaseModel):
    note: SafeFreeText | None = None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "Coffee at Harbor Roasters $12.50 on 2026-11-20",
        "Order 12345 on 2026-11-20 ref 99",
        "123456789012",
        "1234 5678 9012",
        "1234-5678-9012",
        "12345678901234567890",
        "1234 5678 9012 3456 7890",
        "1234-5678-9012-3456-7890",
        "1234 5678-9012 3456-7890",
        "Tracking 12345678901234567890 shipped",
        "Tracking 1234 5678 9012 3456 7890 shipped",
    ],
)
def test_allowed_inputs_pass_sensitive_guard(value: str) -> None:
    """Normal text, 12-digit numbers, and 20-digit tracking numbers are allowed."""
    assert contains_sensitive_digit_sequence(value) is False
    assert validate_no_sensitive_digits(value) == value
    assert _DummyPayload(note=value).note == value


def test_none_is_allowed() -> None:
    """None passes validate_no_sensitive_digits and SafeFreeText | None."""
    assert validate_no_sensitive_digits(None) is None
    assert _DummyPayload(note=None).note is None


@pytest.mark.parametrize(
    "value",
    [
        "1234567890123",
        "123456789012345",
        "4111111111111111",
        "1234567890123456789",
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111 1111-1111 1111",
        "Card 4111 1111 1111 1111 used at store",
        "Ref: 1234-5678-9012-3",
    ],
)
def test_sensitive_13_to_19_digit_sequences_rejected(value: str) -> None:
    """Contiguous, space/hyphen/mixed-separated, and embedded 13-19 digit sequences fail."""
    assert contains_sensitive_digit_sequence(value) is True
    with pytest.raises(ValueError) as exc_info:
        validate_no_sensitive_digits(value)
    assert value not in str(exc_info.value)

    with pytest.raises(ValidationError):
        _DummyPayload(note=value)
