"""Explanation renderer converting structured TraceStep records to sentences (T19, FR-15, NFR-3).

Renders each TraceStep in the caller's exact sequence order into a deterministic,
human-readable sentence with normalized punctuation. Unknown trace types fall back
safely to available trace details without silently dropping steps.
Contains no database, network, clock, or I/O side effects.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.engine.types import TraceStep, _normalize_sequence

_STAGE_PREFIXES: dict[str, str] = {
    "effective_filter": "Effective check",
    "applicability_filter": "Applicability",
    "selection": "Selection",
    "cap_allocation": "Cap allocation",
    "units_calculation": "Units",
    "valuation": "Valuation",
}


def _append_rule_key_if_missing(body: str, rule_key: str | None) -> str:
    """Append rule key context if present and not already included in body."""
    if rule_key is not None and rule_key.strip() and rule_key not in body:
        return f"{body} (rule '{rule_key}')"
    return body


def _fallback_body(step: TraceStep, include_step_type: bool) -> str:
    """Build a deterministic fallback description when step.detail is empty."""
    base = f"Step {step.step_type} ({step.action})" if include_step_type else step.action
    if step.rule_key is not None and step.rule_key.strip():
        base = f"{base} for rule '{step.rule_key}'"
    if step.reason is not None and step.reason.strip():
        base = f"{base} ({step.reason})"
    return base


def render_trace_step(step: TraceStep) -> str:
    """Render a single TraceStep into a deterministic, period-terminated sentence."""
    cleaned_detail = step.detail.strip().rstrip(".")
    prefix = _STAGE_PREFIXES.get(step.step_type)

    if prefix is not None:
        if cleaned_detail:
            body = _append_rule_key_if_missing(cleaned_detail, step.rule_key)
        else:
            body = _fallback_body(step, include_step_type=False)
        return f"{prefix}: {body}."

    if cleaned_detail:
        body = _append_rule_key_if_missing(cleaned_detail, step.rule_key)
        return f"{body}."

    return f"{_fallback_body(step, include_step_type=True)}."


def render_explanation(trace: Sequence[TraceStep]) -> tuple[str, ...]:
    """Render an ordered sequence of TraceStep records into immutable sentences.

    Preserves the caller's exact sequence order and rejects unordered sets.
    """
    normalized = _normalize_sequence(trace, "trace")
    return tuple(render_trace_step(step) for step in normalized)
