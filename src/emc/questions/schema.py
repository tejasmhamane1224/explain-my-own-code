"""Pydantic schemas for comprehension questions, rubrics, and quality gate results."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emc.detect.models import RankedHunk


class QuestionType(str, Enum):
    """5 canonical comprehension question types."""

    PREDICT_OUTPUT = "predict-output"
    WHAT_BREAKS_IF = "what-breaks-if"
    CONSEQUENCE = "consequence"
    SPOT_THE_BUG = "spot-the-bug"
    EXPLAIN_BACK = "explain-back"


class Distractor(BaseModel):
    """An answer option (distractor or correct choice) for multiple choice questions."""

    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Option letter key, e.g. A, B, C, D")
    text: str = Field(description="The answer choice text")
    explanation: str = Field(
        default="",
        description="Reasoning why this option is correct or incorrect",
    )


class RubricCriterion(BaseModel):
    """Evaluation criterion for free-text explain-back questions."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Name of the concept or safety requirement being judged")
    description: str = Field(description="Specific criteria required for full credit")
    points: int = Field(default=1, ge=1, description="Point value for this criterion")
    required_concepts: list[str] = Field(
        default_factory=list,
        description="Concept IDs required to be mentioned or demonstrated",
    )


class QualityGateRejection(BaseModel):
    """Record of a quality gate check failure."""

    model_config = ConfigDict(extra="ignore")

    step: str = Field(
        description=(
            "Validation step that rejected the question: "
            "snippet_grounding, no_answer_leak, independent_solvability, "
            "non_ambiguity, injection_instruction, or schema_violation"
        )
    )
    reason: str = Field(description="Detailed explanation of the rejection")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured context of the failure (e.g. line numbers, leaked tokens)",
    )


class ValidationResult(BaseModel):
    """Overall outcome of the 4-step quality gate on a question candidate."""

    model_config = ConfigDict(extra="ignore")

    passed: bool
    rejections: list[QualityGateRejection] = Field(default_factory=list)
    attempts: int = Field(default=1, ge=1)

    @property
    def primary_rejection(self) -> QualityGateRejection | None:
        return self.rejections[0] if self.rejections else None


class SolverSolution(BaseModel):
    """Output schema for independent solver pass."""

    model_config = ConfigDict(extra="ignore")

    selected_key: str = Field(description="The chosen answer choice key (e.g. A, B, C, D)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="Chain-of-thought or explanation")


class AmbiguityEvaluation(BaseModel):
    """Output schema for ambiguity detection pass."""

    model_config = ConfigDict(extra="ignore")

    is_ambiguous: bool = Field(
        description="True if multiple choices are defensible given the diff alone"
    )
    defensible_choices: list[str] = Field(
        default_factory=list,
        description="List of choice keys (e.g. ['A', 'C']) that could defensibly be argued correct",
    )
    reasoning: str = Field(default="", description="Detailed ambiguity analysis")


class Question(BaseModel):
    """Canonical question model representing a generated comprehension test item."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: QuestionType = Field(description="One of the 5 canonical question types")
    concept_id: str = Field(
        description="Taxonomy concept ID (e.g. anchor.missing_signer, ts.lamport_units)"
    )
    hunk_rank: int = Field(default=1, ge=1, description="Risk rank of the target diff hunk")
    file_path: str = Field(description="Repository-relative file path in the diff")
    start_line: int = Field(ge=1, description="1-indexed starting line number of the snippet")
    end_line: int = Field(ge=1, description="1-indexed ending line number of the snippet")
    snippet: str = Field(description="Verbatim code snippet cited from the diff")
    stem: str = Field(description="The question prompt presented to the user")
    choices: list[Distractor] = Field(
        default_factory=list,
        description="Available answer choices (empty for free-text explain-back)",
    )
    answer_key: str = Field(
        description="The correct answer key (e.g. 'A', 'B') or reference model answer"
    )
    explanation: str = Field(description="Comprehensive explanation of the correct answer")
    rubric: list[RubricCriterion] = Field(
        default_factory=list,
        description="Evaluation rubric for explain-back questions",
    )
    hint_ladder: list[str] = Field(
        default_factory=list,
        description="Ordered hints: 1st subtle, 2nd specific, 3rd near-complete",
    )
    mutant_snippet: str | None = Field(
        default=None,
        description="Mutated copy of snippet with an injected bug (for spot-the-bug questions)",
    )

    def get_correct_choice(self) -> Distractor | None:
        """Find the Distractor corresponding to answer_key."""
        target = self.answer_key.strip().upper()
        for choice in self.choices:
            if choice.key.strip().upper() == target:
                return choice
        return None


class QuestionPlan(BaseModel):
    """Execution plan for generating a single grounded comprehension question."""

    hunk: RankedHunk
    target_concept: str
    recommended_type: QuestionType
    strategy: str = Field(
        description="'templated' for static rule findings, 'llm_open' for open hunks"
    )
    stem_template: str
    prompt_instructions: str
    file_path: str
    start_line: int
    end_line: int
    snippet: str

    @property
    def is_templated(self) -> bool:
        return self.strategy == "templated"
