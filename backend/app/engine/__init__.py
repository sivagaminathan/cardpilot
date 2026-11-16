"""Pure reward engine.

No DB, network, clock, or randomness side effects.
"""

from app.engine.applicability import (
    ApplicabilityResult,
    check_rule_applicability,
    filter_applicable_rules,
)
from app.engine.caps import (
    CapAllocationResult,
    CapPortion,
    allocate_purchase_across_caps,
)
from app.engine.effective import (
    create_no_effective_rule_evaluation,
    filter_effective_rules,
    is_rule_effective,
)
from app.engine.periods import (
    PeriodBounds,
    get_period_bounds,
)
from app.engine.ranking import (
    GLOBAL_COMPARISON_NOTE,
    NO_RANKABLE_CARDS_NOTE,
    RankingResult,
    rank_card_evaluations,
)
from app.engine.selection import (
    SelectionResult,
    create_no_applicable_rule_evaluation,
    select_best_rule,
    sort_rules_by_selection_priority,
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
from app.engine.units import (
    UnitsResult,
    calculate_reward_units,
)
from app.engine.valuation import (
    ValuationResult,
    evaluate_valuation,
)

__all__ = [
    "GLOBAL_COMPARISON_NOTE",
    "NO_RANKABLE_CARDS_NOTE",
    "ApplicabilityResult",
    "AppliedPortion",
    "Cap",
    "CapAllocationResult",
    "CapPortion",
    "CardContext",
    "CardEvaluation",
    "CardStatus",
    "EarningRule",
    "ExclusionType",
    "IneligibleReason",
    "Period",
    "PeriodBounds",
    "PostCapBehavior",
    "Purchase",
    "RankingResult",
    "RoundingMode",
    "Rule",
    "RuleExclusion",
    "ScopeType",
    "SelectionResult",
    "SpendCap",
    "SpendHistory",
    "TraceStep",
    "UnitsResult",
    "UnrankedReason",
    "Valuation",
    "ValuationResult",
    "allocate_purchase_across_caps",
    "calculate_reward_units",
    "check_rule_applicability",
    "create_no_applicable_rule_evaluation",
    "create_no_effective_rule_evaluation",
    "evaluate_valuation",
    "filter_applicable_rules",
    "filter_effective_rules",
    "get_period_bounds",
    "is_rule_effective",
    "rank_card_evaluations",
    "select_best_rule",
    "sort_rules_by_selection_priority",
]
