"""Rubric-based grading engine for free-text explain-back questions."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from emc.grade.deterministic import calculate_hint_penalty
from emc.grade.models import (
    GradeResult,
    RubricCriterionEvaluation,
    RubricEvaluation,
)
from emc.ingest import scan_for_injection_markers
from emc.llm import LLMProvider, ProviderError
from emc.questions.schema import Question, RubricCriterion


class CriterionEvaluationSchema(BaseModel):
    """Schema for individual criterion evaluation from LLM."""

    model_config = ConfigDict(extra="ignore")

    criterion_name: str
    passed: bool
    points_awarded: float = Field(ge=0.0)
    max_points: float = Field(ge=0.0)
    feedback: str = ""


class RubricEvaluationLLMOutput(BaseModel):
    """Structured output expected from LLM rubric judge."""

    model_config = ConfigDict(extra="ignore")

    criteria: list[CriterionEvaluationSchema]
    overall_feedback: str
    passed: bool


_RUBRIC_META_WORDS = {
    "mentions",
    "explains",
    "explanation",
    "description",
    "demonstrates",
    "requires",
    "verifies",
    "criterion",
    "evaluated",
    "understanding",
    "addressed",
    "covered",
    "points",
    "account",
    "code",
    "line",
    "diff",
    "file",
    "anchor",
    "generic",
    "math",
    "ts",
}

_STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "up",
    "about",
    "into",
    "through",
    "after",
    "before",
    "that",
    "this",
    "these",
    "those",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "code",
    "will",
    "would",
    "shall",
    "should",
    "can",
    "could",
    "may",
    "might",
    "must",
    "not",
    "no",
    "nor",
    "too",
    "very",
    "just",
} | _RUBRIC_META_WORDS


def _extract_keywords(text: str) -> set[str]:
    """Extract informative lowercase keywords from text."""
    words = re.findall(r"[a-z0-9_]{3,}", text.lower())
    return {w for w in words if w not in _STOP_WORDS}


def deterministic_rubric_fallback(
    question: Question,
    user_answer: str,
    passing_threshold: float = 70.0,
) -> RubricEvaluation:
    """Evaluate explain-back answer deterministically without LLM provider calls.

    Inspects user answer for required concept identifiers, taxonomy tokens,
    and descriptive keywords specified in the question rubric.
    """
    cleaned = user_answer.strip().lower()
    user_words = _extract_keywords(cleaned)

    # Require substantive explanation content (at least 2 domain words and 15 chars)
    if len(cleaned) < 15 or len(user_words) < 2:
        return RubricEvaluation(
            criteria_results=[
                RubricCriterionEvaluation(
                    criterion_name=c.name,
                    passed=False,
                    points_awarded=0.0,
                    max_points=float(c.points),
                    feedback="No substantive explanation provided.",
                )
                for c in (
                    question.rubric
                    or [
                        RubricCriterion(
                            name="Explanation", description="Concept explanation", points=1
                        )
                    ]
                )
            ],
            total_score=0.0,
            max_score=float(sum(c.points for c in question.rubric)) if question.rubric else 1.0,
            overall_feedback="Explanation too brief or lacking substantive domain keywords.",
            passed=False,
        )

    criteria = question.rubric
    if not criteria:
        criteria = [
            RubricCriterion(
                name="Concept Understanding",
                description=f"Demonstrates understanding of {question.concept_id}",
                points=1,
                required_concepts=[question.concept_id],
            )
        ]

    evaluations: list[RubricCriterionEvaluation] = []
    total_earned = 0.0
    total_possible = 0.0

    for crit in criteria:
        max_pts = float(crit.points)
        total_possible += max_pts

        # 1. Concept matching: check explicit required_concepts if specified,
        # otherwise strip namespace prefix from question.concept_id.
        concept_match = False
        target_concepts = list(crit.required_concepts)
        if not target_concepts:
            clean_concept_id = re.sub(r"^(?:anchor|ts|generic|math)\.", "", question.concept_id)
            target_concepts = [clean_concept_id]

        for concept in target_concepts:
            clean_concept = re.sub(r"^(?:anchor|ts|generic|math)\.", "", concept.lower())
            concept_tokens = [
                t
                for t in re.split(r"[._\s]+", clean_concept)
                if len(t) >= 3 and t not in _RUBRIC_META_WORDS
            ]
            for token in concept_tokens:
                # Word-boundary regex search to prevent substring collisions
                if re.search(rf"\b{re.escape(token)}\b", cleaned):
                    concept_match = True
                    break
            if concept_match:
                break

        # 2. Keyword density matching
        crit_keywords = _extract_keywords(f"{crit.name} {crit.description}")
        matched_keywords = user_words.intersection(crit_keywords)
        if len(crit_keywords) <= 1:
            keyword_match = len(matched_keywords) >= 1
        else:
            keyword_match = len(matched_keywords) >= 2 and (
                len(matched_keywords) / len(crit_keywords) >= 0.25
            )

        passed = concept_match or keyword_match
        pts = max_pts if passed else 0.0
        total_earned += pts

        if passed:
            feedback = f"Criterion '{crit.name}' satisfied."
        else:
            feedback = f"Missing key explanation points for '{crit.name}'."

        evaluations.append(
            RubricCriterionEvaluation(
                criterion_name=crit.name,
                passed=passed,
                points_awarded=pts,
                max_points=max_pts,
                feedback=feedback,
            )
        )

    ratio = (total_earned / total_possible) if total_possible > 0 else 0.0
    overall_passed = (ratio * 100.0) >= passing_threshold

    return RubricEvaluation(
        criteria_results=evaluations,
        total_score=round(total_earned, 2),
        max_score=round(total_possible, 2),
        overall_feedback=(
            "Explanation demonstrated acceptable understanding of diff safety requirements."
            if overall_passed
            else "Explanation did not sufficiently address the rubric criteria."
        ),
        passed=overall_passed,
    )


def grade_rubric(
    question: Question,
    user_answer: str,
    provider: LLMProvider | None = None,
    hints_used: int = 0,
    base_points: float = 10.0,
    penalty_per_hint: float = 0.25,
    max_hint_penalty: float = 0.75,
    passing_threshold: float = 70.0,
) -> GradeResult:
    """Grade an explain-back free-text response using LLM judge or deterministic fallback."""
    raw = user_answer.strip()

    # Skip handling
    if raw.lower() in ("skip", "s", "--skip"):
        return GradeResult(
            question_id=question.id,
            question_type=question.type,
            concept_id=question.concept_id,
            user_answer=user_answer,
            is_correct=False,
            base_points=base_points,
            points_awarded=0.0,
            max_points=base_points,
            hints_used=hints_used,
            hint_penalty_percent=0.0,
            explanation=question.explanation,
            feedback="Question skipped.",
            is_skipped=True,
        )

    # Prompt injection check
    injection_warnings = scan_for_injection_markers(raw)
    adversarial_override = bool(
        re.search(
            r"\b(?:ignore\s+(?:all|previous|above)\s+instructions|system\s+prompt|passed\s*:\s*true)\b",
            raw,
            re.IGNORECASE,
        )
    )
    if injection_warnings or adversarial_override:
        return GradeResult(
            question_id=question.id,
            question_type=question.type,
            concept_id=question.concept_id,
            user_answer=user_answer,
            is_correct=False,
            base_points=base_points,
            points_awarded=0.0,
            max_points=base_points,
            hints_used=hints_used,
            hint_penalty_percent=0.0,
            explanation=question.explanation,
            feedback="Adversarial or prompt injection pattern detected in answer.",
            is_skipped=False,
        )

    rubric_eval: RubricEvaluation | None = None

    if provider is not None:
        rubric_text = "\n".join(
            f"- {c.name}: {c.description} ({c.points} pts, "
            f"required concepts: {c.required_concepts})"
            for c in question.rubric
        )
        prompt = (
            "Evaluate the developer's explanation against the diff and rubric.\n\n"
            f"FILE: {question.file_path}:{question.start_line}-{question.end_line}\n"
            f"CODE SNIPPET:\n```\n{question.snippet}\n```\n\n"
            f"QUESTION STEM:\n{question.stem}\n\n"
            f"REFERENCE EXPLANATION:\n{question.explanation}\n\n"
            f"RUBRIC CRITERIA:\n{rubric_text}\n\n"
            f"DEVELOPER'S EXPLANATION:\n{user_answer}\n\n"
            "Score each criterion strictly. Return structured JSON."
        )
        system_prompt = (
            "You are an expert security engineer and code reviewer grading an interactive "
            "comprehension assessment. Evaluate whether the developer's explanation demonstrates "
            "actual understanding of the risks, invariants, and mechanisms in the diff."
        )
        try:
            resp = provider.generate_structured(
                prompt=prompt,
                schema=RubricEvaluationLLMOutput,
                system=system_prompt,
            )
            if resp.structured is not None:
                llm_result = resp.structured
                criteria_results = [
                    RubricCriterionEvaluation(
                        criterion_name=c.criterion_name,
                        passed=c.passed,
                        points_awarded=max(0.0, min(float(c.points_awarded), float(c.max_points))),
                        max_points=max(0.0, float(c.max_points)),
                        feedback=c.feedback,
                    )
                    for c in llm_result.criteria
                ]
                total_earned = sum(c.points_awarded for c in criteria_results)
                total_max = sum(c.max_points for c in criteria_results)
                rubric_eval = RubricEvaluation(
                    criteria_results=criteria_results,
                    total_score=round(total_earned, 2),
                    max_score=round(total_max, 2),
                    overall_feedback=llm_result.overall_feedback,
                    passed=llm_result.passed,
                )
        except ProviderError:
            rubric_eval = None

    # Fallback to deterministic rubric evaluation if LLM was unavailable or failed
    if rubric_eval is None:
        rubric_eval = deterministic_rubric_fallback(
            question=question,
            user_answer=user_answer,
            passing_threshold=passing_threshold,
        )

    score_ratio = (
        (rubric_eval.total_score / rubric_eval.max_score)
        if rubric_eval.max_score > 0
        else (1.0 if rubric_eval.passed else 0.0)
    )
    score_ratio = max(0.0, min(1.0, score_ratio))

    penalty = calculate_hint_penalty(hints_used, penalty_per_hint, max_hint_penalty)
    awarded = round(base_points * score_ratio * (1.0 - penalty), 2)
    awarded = max(0.0, min(base_points, awarded))
    is_correct = rubric_eval.passed or (score_ratio * 100.0 >= passing_threshold)

    penalty_desc = f" ({int(penalty * 100)}% hint penalty)" if penalty > 0 else ""
    status_str = "Passed" if is_correct else "Needs improvement"
    feedback = (
        f"{status_str}: Earned {awarded:.1f} / {base_points:.1f} pts{penalty_desc}. "
        f"{rubric_eval.overall_feedback}"
    )

    return GradeResult(
        question_id=question.id,
        question_type=question.type,
        concept_id=question.concept_id,
        user_answer=user_answer,
        is_correct=is_correct,
        base_points=base_points,
        points_awarded=awarded,
        max_points=base_points,
        hints_used=hints_used,
        hint_penalty_percent=penalty,
        rubric_evaluation=rubric_eval,
        explanation=question.explanation,
        feedback=feedback,
        is_skipped=False,
    )
