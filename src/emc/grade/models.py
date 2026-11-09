"""Pydantic schemas and data models for comprehension grading, rubrics, and scores."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emc.questions.schema import QuestionType


class RubricCriterionEvaluation(BaseModel):
    """Evaluation result for a single rubric criterion."""

    model_config = ConfigDict(extra="ignore")

    criterion_name: str = Field(description="Name of the evaluated criterion")
    passed: bool = Field(description="Whether the criterion requirements were satisfied")
    points_awarded: float = Field(ge=0.0, description="Points awarded for this criterion")
    max_points: float = Field(ge=0.0, description="Maximum points possible for this criterion")
    feedback: str = Field(default="", description="Targeted feedback explaining the evaluation")


class RubricEvaluation(BaseModel):
    """Comprehensive rubric evaluation for free-text explain-back questions."""

    model_config = ConfigDict(extra="ignore")

    criteria_results: list[RubricCriterionEvaluation] = Field(default_factory=list)
    total_score: float = Field(ge=0.0, description="Total points earned across all criteria")
    max_score: float = Field(ge=0.0, description="Maximum possible points across all criteria")
    overall_feedback: str = Field(default="", description="Summary feedback for the response")
    passed: bool = Field(
        default=False, description="Whether the response met the passing threshold"
    )


class GradeResult(BaseModel):
    """Grading result for a single question item."""

    model_config = ConfigDict(extra="ignore")

    question_id: str
    question_type: QuestionType
    concept_id: str
    user_answer: str
    is_correct: bool
    base_points: float = Field(default=10.0, ge=0.0)
    points_awarded: float = Field(default=0.0, ge=0.0)
    max_points: float = Field(default=10.0, ge=0.0)
    hints_used: int = Field(default=0, ge=0)
    hint_penalty_percent: float = Field(default=0.0, ge=0.0, le=1.0)
    rubric_evaluation: RubricEvaluation | None = None
    explanation: str = Field(default="")
    feedback: str = Field(default="")
    is_skipped: bool = Field(default=False)


class ScoreBreakdown(BaseModel):
    """Aggregated score summary across all questions in a session."""

    model_config = ConfigDict(extra="ignore")

    total_questions: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    total_hints_used: int = Field(default=0, ge=0)
    points_earned: float = Field(default=0.0, ge=0.0)
    points_possible: float = Field(default=0.0, ge=0.0)
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    passed: bool = Field(default=False)
    passing_threshold: float = Field(default=70.0, ge=0.0, le=100.0)
    results: list[GradeResult] = Field(default_factory=list)

    @classmethod
    def from_results(
        cls,
        results: list[GradeResult],
        passing_threshold: float = 70.0,
    ) -> ScoreBreakdown:
        """Aggregate individual question grade results into a session summary."""
        total_q = len(results)
        if total_q == 0:
            return cls(passing_threshold=passing_threshold)

        correct = sum(1 for r in results if r.is_correct)
        skipped = sum(1 for r in results if r.is_skipped)
        hints = sum(r.hints_used for r in results)
        earned = sum(r.points_awarded for r in results)
        possible = sum(r.max_points for r in results)
        pct = round((earned / possible * 100.0), 2) if possible > 0 else 0.0
        is_passed = (pct >= passing_threshold) and (correct > 0 or earned > 0)

        return cls(
            total_questions=total_q,
            correct_count=correct,
            skipped_count=skipped,
            total_hints_used=hints,
            points_earned=round(earned, 2),
            points_possible=round(possible, 2),
            percentage=pct,
            passed=is_passed,
            passing_threshold=passing_threshold,
            results=results,
        )
