"""Pydantic models for event ledger, Leitner box mastery, and reports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MasteryLevel(str, Enum):
    """5-stage mastery levels corresponding to Leitner boxes 1 to 5."""

    WEAK = "Weak"
    DEVELOPING = "Developing"
    COMPETENT = "Competent"
    PROFICIENT = "Proficient"
    MASTERED = "Mastered"

    @classmethod
    def from_box(cls, box: int) -> MasteryLevel:
        """Map Leitner box number (1-5) to canonical mastery level."""
        mapping = {
            1: cls.WEAK,
            2: cls.DEVELOPING,
            3: cls.COMPETENT,
            4: cls.PROFICIENT,
            5: cls.MASTERED,
        }
        return mapping.get(box, cls.WEAK)


class LedgerEvent(BaseModel):
    """Single question attempt event stored in .emc/ledger.jsonl."""

    model_config = ConfigDict(extra="ignore")

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of attempt",
    )
    session_id: str = Field(description="Unique identifier for quiz or review session")
    diff_hash: str = Field(default="", description="Content hash of the analyzed diff")
    concept_id: str = Field(description="Taxonomy concept ID")
    question_type: str = Field(description="Question type identifier")
    user_answer: str = Field(description="Submitted answer string")
    is_correct: bool = Field(description="Whether the answer was graded correct")
    hints_used: int = Field(default=0, ge=0, description="Number of hints revealed")
    points_awarded: float = Field(default=0.0, ge=0.0, description="Points earned")
    max_points: float = Field(default=10.0, ge=0.0, description="Maximum possible points")
    question_id: str = Field(default="", description="Optional question identifier")
    is_skipped: bool = Field(default=False, description="Whether question was skipped")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ConceptMastery(BaseModel):
    """Current mastery state for a single concept in Leitner box system."""

    model_config = ConfigDict(extra="ignore")

    concept_id: str = Field(description="Canonical concept ID")
    name: str = Field(description="Human-readable concept name")
    category: str = Field(default="generic", description="Taxonomy category")
    box: int = Field(default=1, ge=1, le=5, description="Leitner box number (1 to 5)")
    attempts: int = Field(default=0, ge=0, description="Total questions answered")
    correct_count: int = Field(default=0, ge=0, description="Total correct answers")
    streak: int = Field(default=0, ge=0, description="Current consecutive correct answers")
    pass_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="Pass percentage")
    last_reviewed: str | None = Field(
        default=None, description="ISO-8601 timestamp of last attempt"
    )
    mastery_level: MasteryLevel = Field(default=MasteryLevel.WEAK, description="Mastery status")

    @property
    def box_visual(self) -> str:
        """Visual bar representation of Leitner box (e.g. [■■□□□] Box 2 or [##---] on cp1252)."""
        import sys

        can_unicode = True
        try:
            encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            "\u25a0\u25a1".encode(encoding)
        except Exception:
            can_unicode = False

        if can_unicode:
            filled = "\u25a0" * self.box
            empty = "\u25a1" * (5 - self.box)
        else:
            filled = "#" * self.box
            empty = "-" * (5 - self.box)
        return f"[{filled}{empty}] Box {self.box}"

    @property
    def is_weak(self) -> bool:
        """Whether concept requires reinforcement (Box 1 or Box 2)."""
        return self.box <= 2


class MasterySummary(BaseModel):
    """Aggregate mastery metrics across all taxonomy concepts."""

    model_config = ConfigDict(extra="ignore")

    total_questions: int = Field(default=0, ge=0, description="Total question attempts")
    total_correct: int = Field(default=0, ge=0, description="Total correct attempts")
    accuracy_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Overall accuracy %")
    mastered_count: int = Field(default=0, ge=0, description="Concepts in Box 5 (Mastered)")
    proficient_count: int = Field(default=0, ge=0, description="Concepts in Box 4 (Proficient)")
    competent_count: int = Field(default=0, ge=0, description="Concepts in Box 3 (Competent)")
    developing_count: int = Field(default=0, ge=0, description="Concepts in Box 2 (Developing)")
    weak_count: int = Field(default=0, ge=0, description="Concepts in Box 1 (Weak)")
    active_concepts: int = Field(default=0, ge=0, description="Concepts with at least 1 attempt")
    total_concepts: int = Field(default=0, ge=0, description="Total concepts in taxonomy")
