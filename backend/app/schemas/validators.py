"""Shared Pydantic validators for cardholder input safety (T30, AC-12)."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_DIGIT_SEQUENCE_RE = re.compile(r"\d(?:[ -]?\d)*")


def contains_sensitive_digit_sequence(value: str) -> bool:
    """Return True if ``value`` has a 13-19 digit sequence (optionally space/hyphen-separated)."""
    for match in _DIGIT_SEQUENCE_RE.finditer(value):
        digit_count = sum(ch.isdigit() for ch in match.group(0))
        if 13 <= digit_count <= 19:
            return True
    return False


def validate_no_sensitive_digits(value: str | None) -> str | None:
    """Reject strings containing 13-19 digit sequences without echoing input."""
    if value is not None and contains_sensitive_digit_sequence(value):
        raise ValueError("Input must not contain a 13-19 digit sequence (possible card number).")
    return value


SafeFreeText = Annotated[str, AfterValidator(validate_no_sensitive_digits)]
