"""Comprehension grading module for explain-my-own-code (emc)."""

from emc.grade.deterministic import (
    calculate_hint_penalty,
    grade_deterministic,
    match_choice_key,
    match_spot_the_bug,
    normalize_input,
)
from emc.grade.models import (
    GradeResult,
    RubricCriterionEvaluation,
    RubricEvaluation,
    ScoreBreakdown,
)
from emc.grade.rubric import (
    deterministic_rubric_fallback,
    grade_rubric,
)

__all__ = [
    "GradeResult",
    "RubricCriterionEvaluation",
    "RubricEvaluation",
    "ScoreBreakdown",
    "calculate_hint_penalty",
    "deterministic_rubric_fallback",
    "grade_deterministic",
    "grade_rubric",
    "match_choice_key",
    "match_spot_the_bug",
    "normalize_input",
]
