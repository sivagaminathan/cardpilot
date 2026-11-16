"""Pure reward engine.

No DB, network, clock, or randomness side effects.
"""

from app.engine.applicability import (
    ApplicabilityResult,
    check_rule_applicability,
    filter_applicable_rules,
)
from app.engine.effective import (
    create_no_effective_rule_evaluation,
    filter_effective_rules,
    is_rule_effective,
)
from app.engine.types import (
    AppliedPortion,
    Cap,
    CardContext,
    CardEvaluation,
    CardStatus,
    EarningRule,
    ExclusionType,
    IneligibleReason,
    Period,
    PostCapBehavior,
    Purchase,
    RoundingMode,
    Rule,
    RuleExclusion,
    ScopeType,
    SpendCap,
    SpendHistory,
    TraceStep,
    UnrankedReason,
    Valuation,
)

__all__ = [
    "ApplicabilityResult",
    "AppliedPortion",
    "Cap",
    "CardContext",
    "CardEvaluation",
    "CardStatus",
    "EarningRule",
    "ExclusionType",
    "IneligibleReason",
    "Period",
    "PostCapBehavior",
    "Purchase",
    "RoundingMode",
    "Rule",
    "RuleExclusion",
    "ScopeType",
    "SpendCap",
    "SpendHistory",
    "TraceStep",
    "UnrankedReason",
    "Valuation",
    "check_rule_applicability",
    "create_no_effective_rule_evaluation",
    "filter_applicable_rules",
    "filter_effective_rules",
    "is_rule_effective",
]
